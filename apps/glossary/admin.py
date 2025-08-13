# apps/glossary/admin.py
from django.contrib import admin
from django import forms
from django.http import HttpResponse
from django.urls import path
from django.utils.html import format_html

from .models import GlossaryNode, GlossaryType

# Langues exposées en admin (ajoute "de", "it" quand tu veux)
LANGS = ["fr", "en", "de", "it"]


class GlossaryNodeForm(forms.ModelForm):
    """
    Form Admin :
      - champs 'plats' par langue, mappés vers JSONFields (labels/definition/procede/explication_technique/seo)
      - masquage live via Media.js selon le type
    """

    # Labels
    label_fr = forms.CharField(required=True, label="Label (fr)")
    label_en = forms.CharField(required=True, label="Label (en)")
    label_de = forms.CharField(required=False, label="Label (de)")
    label_it = forms.CharField(required=False, label="Label (it)")

    # Definition (metier & operation)
    definition_fr = forms.CharField(required=False, widget=forms.Textarea, label="Définition (fr)")
    definition_en = forms.CharField(required=False, widget=forms.Textarea, label="Définition (en)")
    definition_de = forms.CharField(required=False, widget=forms.Textarea, label="Définition (de)")
    definition_it = forms.CharField(required=False, widget=forms.Textarea, label="Définition (it)")

    # Procédé (operation)
    procede_fr = forms.CharField(required=False, widget=forms.Textarea, label="Procédé (fr)")
    procede_en = forms.CharField(required=False, widget=forms.Textarea, label="Procédé (en)")
    procede_de = forms.CharField(required=False, widget=forms.Textarea, label="Procédé (de)")
    procede_it = forms.CharField(required=False, widget=forms.Textarea, label="Procédé (it)")

    # Explication technique (variante)
    explication_technique_fr = forms.CharField(required=False, widget=forms.Textarea, label="Explication technique (fr)")
    explication_technique_en = forms.CharField(required=False, widget=forms.Textarea, label="Explication technique (en)")
    explication_technique_de = forms.CharField(required=False, widget=forms.Textarea, label="Explication technique (de)")
    explication_technique_it = forms.CharField(required=False, widget=forms.Textarea, label="Explication technique (it)")

    # SEO (keywords CSV + description)
    seo_keywords_fr = forms.CharField(required=False, label="SEO keywords (fr, CSV)")
    seo_keywords_en = forms.CharField(required=False, label="SEO keywords (en, CSV)")
    seo_keywords_de = forms.CharField(required=False, label="SEO keywords (de, CSV)")
    seo_keywords_it = forms.CharField(required=False, label="SEO keywords (it, CSV)")

    seo_description_fr = forms.CharField(required=False, widget=forms.Textarea, label="SEO description (fr)")
    seo_description_en = forms.CharField(required=False, widget=forms.Textarea, label="SEO description (en)")
    seo_description_de = forms.CharField(required=False, widget=forms.Textarea, label="SEO description (de)")
    seo_description_it = forms.CharField(required=False, widget=forms.Textarea, label="SEO description (it)")

    class Meta:
        model = GlossaryNode
        fields = [
            "glossary_id", "node_id", "type", "parent", "path",
            "embedding", "is_active", "version", "alerts",
            "created_by", "reviewed_by",
        ]
        widgets = {"path": forms.TextInput(attrs={"readonly": "readonly"})}

    class Media:
        # crée "glossary_admin.js" dans STATIC_ROOT pour le masquage live des fieldsets
        js = ("glossary/glossary_admin.js",)

    # ---- Préremplissage depuis les JSONFields ----
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = getattr(self, "instance", None)
        if inst and inst.pk:
            for lang in LANGS:
                self.fields[f"label_{lang}"].initial = (inst.labels or {}).get(lang, "")
                self.fields[f"definition_{lang}"].initial = (inst.definition or {}).get(lang, "")
                self.fields[f"procede_{lang}"].initial = (inst.procede or {}).get(lang, "")
                self.fields[f"explication_technique_{lang}"].initial = (inst.explication_technique or {}).get(lang, "")
                seo_lang = (inst.seo or {}).get(lang, {})
                kws = seo_lang.get("keywords", [])
                self.fields[f"seo_keywords_{lang}"].initial = ", ".join(kws) if isinstance(kws, list) else ""
                self.fields[f"seo_description_{lang}"].initial = seo_lang.get("description", "")

    # ---- Validation & mapping vers JSON ----
    def clean(self):
        cleaned = super().clean()

        # labels JSON (FR/EN requis)
        labels = {lang: (cleaned.get(f"label_{lang}") or "") for lang in LANGS if cleaned.get(f"label_{lang}")}
        if not labels.get("fr") or not labels.get("en"):
            raise forms.ValidationError("Les labels fr et en sont requis.")
        cleaned["labels_json"] = labels

        def pack(prefix):
            return {lang: (cleaned.get(f"{prefix}_{lang}") or "") for lang in LANGS if cleaned.get(f"{prefix}_{lang}")}

        cleaned["definition_json"] = pack("definition")
        cleaned["procede_json"] = pack("procede")
        cleaned["explication_technique_json"] = pack("explication_technique")

        seo = {}
        for lang in LANGS:
            kws = [k.strip() for k in (cleaned.get(f"seo_keywords_{lang}") or "").split(",") if k.strip()]
            desc = cleaned.get(f"seo_description_{lang}") or ""
            if kws or desc:
                seo[lang] = {"keywords": kws, "description": desc}
        cleaned["seo_json"] = seo

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        c = self.cleaned_data
        obj.labels = c.get("labels_json", {})
        obj.definition = c.get("definition_json", {})
        obj.procede = c.get("procede_json", {})
        obj.explication_technique = c.get("explication_technique_json", {})
        obj.seo = c.get("seo_json", {})
        if commit:
            obj.save()
            self.save_m2m()
        return obj


@admin.register(GlossaryNode)
class GlossaryNodeAdmin(admin.ModelAdmin):
    form = GlossaryNodeForm

    list_display = ("glossary_id", "type", "type_badge", "label_fr", "lang_status", "parent", "path", "updated_at", "is_active", "version")
    list_filter = ("type", "is_active")
    search_fields = ("glossary_id", "node_id", "path", "labels")
    ordering = ("path",)
    readonly_fields = ("path", "created_at", "updated_at", "version")

    fieldsets = (
        ("Identité", {
            "fields": ("glossary_id", "node_id", "type", "parent", "path", "is_active", "version", "alerts")
        }),
        ("Labels", {
            "fields": tuple(f"label_{l}" for l in LANGS)
        }),
        ("Définition (métier & opération)", {
            "fields": tuple(f"definition_{l}" for l in LANGS)
        }),
        ("Procédé (opération seulement)", {
            "fields": tuple(f"procede_{l}" for l in LANGS)
        }),
        ("Explication technique (variante seulement)", {
            "fields": tuple(f"explication_technique_{l}" for l in LANGS)
        }),
        ("SEO", {
            "fields": tuple(f"seo_keywords_{l}" for l in LANGS) + tuple(f"seo_description_{l}" for l in LANGS)
        }),
        ("Trace", {
            "fields": ("created_at", "updated_at", "created_by", "reviewed_by")
        }),
    )

    # accès rapide au label FR dans la liste
    def label_fr(self, obj):
        return (obj.labels or {}).get("fr", "")
    label_fr.short_description = "Label (fr)"

    def type_badge(self, obj):
        color = {
            "metier": "#007bff",       # bleu
            "operation": "#28a745",    # vert
            "variante": "#ffc107",     # jaune
        }.get(obj.type, "#6c757d")     # gris par défaut
        label = dict(GlossaryType.choices).get(obj.type, obj.type)
        return format_html(
            f"<span style='background:{color}; color:white; padding:2px 6px; border-radius:4px;'>{label}</span>"
        )
    type_badge.short_description = "Type"

    def lang_status(self, obj):
        langs = ["fr", "en", "de", "it"]
        labels = obj.labels or {}
        icons = []
        for lang in langs:
            if labels.get(lang):
                icons.append(f"<span style='color:green;'>✔️ {lang}</span>")
            else:
                icons.append(f"<span style='color:gray;'>❌ {lang}</span>")
        return format_html(" | ".join(icons))
    lang_status.short_description = "Langues"


    # Action : Valider (version +1)
    actions = ["approve_nodes"]

    @admin.action(description="Valider (version +1)")
    def approve_nodes(self, request, queryset):
        updated = 0
        for n in queryset:
            n.version = (n.version or 0) + 1
            n.reviewed_by = request.user
            n.save(update_fields=["version", "reviewed_by", "updated_at"])
            updated += 1
        self.message_user(request, f"{updated} nœud(s) validé(s).")

    # Export JSON (bouton + endpoint)
    def get_urls(self):
        urls = super().get_urls()
        custom = [path("export-json/", self.admin_site.admin_view(self.export_json), name="glossary_export_json")]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["custom_button"] = format_html(
            '<a class="button" href="{}" style="margin:10px;">📤 Exporter le glossaire JSON</a>',
            "../export-json/",
        )
        return super().changelist_view(request, extra_context=extra_context)

    def export_json(self, request):
        import json
        qs = GlossaryNode.objects.all().order_by("path")
        payload = [{
            "glossary_id": n.glossary_id,
            "node_id": n.node_id,
            "type": n.type,
            "parent_glossary_id": n.parent.glossary_id if n.parent else None,
            "path": n.path,
            "labels": n.labels,
            "definition": n.definition,
            "procede": n.procede,
            "explication_technique": n.explication_technique,
            "seo": n.seo,
            "is_active": n.is_active,
            "version": n.version,
            "alerts": n.alerts or [],
        } for n in qs]
        data = json.dumps(payload, ensure_ascii=False, indent=2)
        resp = HttpResponse(data, content_type="application/json; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename=\"glossary_export.json\"'
        return resp
