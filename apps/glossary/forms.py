# apps/glossary/forms.py
from django import forms
from .models import GlossaryNode

LANGS = ["fr", "en"]

class GlossaryNodeForm(forms.ModelForm):
    """
    Formulaire Admin pour GlossaryNode :
    - Champs plats par langue, mappés vers JSONB (labels/definition/procede/explication_technique/seo).
    - Masquage dynamique via glossary_admin.js selon le type.
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
        ] + [f"label_{l}" for l in LANGS] + \
            [f"definition_{l}" for l in LANGS] + \
            [f"procede_{l}" for l in LANGS] + \
            [f"explication_technique_{l}" for l in LANGS] + \
            [f"seo_keywords_{l}" for l in LANGS] + \
            [f"seo_description_{l}" for l in LANGS]

    class Media:
        js = ("glossary/glossary_admin.js",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = getattr(self, "instance", None)
        if inst and inst.pk:
            for lang in LANGS + ["de", "it"]:
                self.fields[f"label_{lang}"].initial = (inst.labels or {}).get(lang, "")
                self.fields[f"definition_{lang}"].initial = (inst.definition or {}).get(lang, "")
                self.fields[f"procede_{lang}"].initial = (inst.procede or {}).get(lang, "")
                self.fields[f"explication_technique_{lang}"].initial = (inst.explication_technique or {}).get(lang, "")
                seo_lang = (inst.seo or {}).get(lang, {})
                kws = seo_lang.get("keywords", [])
                self.fields[f"seo_keywords_{lang}"].initial = ", ".join(kws) if isinstance(kws, list) else ""
                self.fields[f"seo_description_{lang}"].initial = seo_lang.get("description", "")

    def clean(self):
        cleaned = super().clean()
        labels = {lang: (cleaned.get(f"label_{lang}") or "") for lang in LANGS + ["de", "it"] if cleaned.get(f"label_{lang}")}
        if not labels.get("fr") or not labels.get("en"):
            raise forms.ValidationError("Les labels fr et en sont requis.")
        cleaned["labels_json"] = labels

        def pack(prefix):
            return {lang: (cleaned.get(f"{prefix}_{lang}") or "") for lang in LANGS + ["de", "it"] if cleaned.get(f"{prefix}_{lang}")}

        cleaned["definition_json"] = pack("definition")
        cleaned["procede_json"] = pack("procede")
        cleaned["explication_technique_json"] = pack("explication_technique")

        seo = {}
        for lang in LANGS + ["de", "it"]:
            kws = [k.strip() for k in (cleaned.get(f"seo_keywords_{lang}") or "").split(",") if k.strip()]
            desc = cleaned.get(f"seo_description_{lang}") or ""
            if kws or desc:
                seo[lang] = {"keywords": kws, "description": desc}
        cleaned["seo_json"] = seo

        # Valider les règles métier du modèle
        instance = GlossaryNode(
            type=cleaned.get("type"),
            parent=cleaned.get("parent"),
            labels=cleaned["labels_json"],
            definition=cleaned["definition_json"],
            procede=cleaned["procede_json"],
            explication_technique=cleaned["explication_technique_json"],
            seo=cleaned["seo_json"],
        )
        instance.clean()

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