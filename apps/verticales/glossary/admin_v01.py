# apps/glossary/admin.py

from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html, format_html_join

from .models import GlossaryNode
from .forms import GlossaryNodeForm
from .tasks import run_generate_glossary, sync_embeddings_to_faiss
from apps.language.utils import get_active_langs
from apps.language.utils import get_default_lang
from django.db.models.expressions import RawSQL
from apps.language.models import Language
from django import forms
from django.template.response import TemplateResponse
from apps.language.tasks import translate_glossary_nodes

class TranslateWizardForm(forms.Form):
    source_lang = forms.ChoiceField(label="Langue source")
    target_langs = forms.MultipleChoiceField(
        label="Langues cibles",
        help_text="Sélectionne les langues à remplir (peuvent être inactives).",
        widget=forms.SelectMultiple
    )
    only_missing = forms.BooleanField(
        label="Compléter uniquement les champs manquants",
        initial=True, required=False
    )
    include_seo = forms.BooleanField(
        label="Inclure les champs SEO (title/keywords/description)",
        initial=True, required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        langs = list(Language.objects.order_by("-is_default", "name").values_list("code", "name"))
        choices = [(code, f"{name} ({code})") for code, name in langs]
        self.fields["source_lang"].choices = choices
        self.fields["target_langs"].choices = choices

# --- Filtres custom ---

class AValiderFilter(SimpleListFilter):
    title = _("À valider")
    parameter_name = "a_valider"

    def lookups(self, request, model_admin):
        return [
            ("yes", _("À valider")),
            ("no", _("Validé")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(is_active=False, reviewed_by__isnull=True)
        if self.value() == "no":
            return queryset.filter(is_active=True, reviewed_by__isnull=False)
        return queryset


class AlertTypeFilter(SimpleListFilter):
    """
    Filtre par type d'alerte IA.
    Utilise une condition JSONB robuste (nécessite PostgreSQL).
    """
    title = _("Alertes IA")
    parameter_name = "alert_type"

    def lookups(self, request, model_admin):
        return [
            ("ia_pending", _("En attente IA")),
            ("ia_processed", _("IA traitée")),
            ("ia_error", _("Erreur IA")),
        ]

    def queryset(self, request, queryset):
        val = self.value()
        if not val:
            return queryset
        # Équivalent à: EXISTS (SELECT 1 FROM jsonb_array_elements(alerts) a WHERE a->>'type' = val)
        return queryset.extra(
            where=["EXISTS (SELECT 1 FROM jsonb_array_elements(alerts) AS a WHERE a->>'type' = %s)"],
            params=[val],
        )

class MissingLangFilter(admin.SimpleListFilter):
    title = "Incomplet (langue)"
    parameter_name = "missing_lang"

    def lookups(self, request, model_admin):
        return [(c, c.upper()) for c in get_active_langs()]

    def queryset(self, request, qs):
        lang = self.value()
        if not lang:
            return qs
        # Exemple: considérons 'incomplet' si label OU seo.description manquent
        return qs.extra(
            where=[
                "coalesce(labels->>%s, '') = '' OR "
                "coalesce((seo->%s->>'description')::text, '') = ''"
            ],
            params=[lang, lang],
        )
@admin.register(GlossaryNode)
class GlossaryNodeAdmin(admin.ModelAdmin):
    list_filter = (..., MissingLangFilter)
    actions = ("action_translate_missing", "action_mark_reviewed", ...)

    # Affichage liste
    list_display = ("type", "path", "is_active", "version", "ia_status", "updated_at")
    list_filter = ("type", "is_active", AValiderFilter, AlertTypeFilter)
    search_fields = ("search_text", "path", "node_id", "glossary_id")

    # Champs non éditables
    readonly_fields = (
        "glossary_id", "path", "search_text",
        "created_at", "updated_at",
        "ia_status", "alerts_pretty",
    )

    # Actions rapides
    actions = ("action_trigger_ia", "action_sync_faiss", "action_mark_reviewed")

    # Organisation des onglets/sections
    def get_fieldsets(self, request, obj=None):
        # Champs multilingues dynamiques (créés par la Form)
        base_fields = [f"label_{lang}" for lang in ACTIVE_LANGS]
        definition_fields = [f"definition_{lang}" for lang in ACTIVE_LANGS]
        seo_fields = [f"seo_keywords_{lang}" for lang in ACTIVE_LANGS] + [f"seo_description_{lang}" for lang in ACTIVE_LANGS]

        fieldsets = [
            (_("Identification"), {"fields": ("type", "parent", "node_id", "glossary_id", "path")}),
            (_("Labels"), {"fields": base_fields}),
            (_("Definitions"), {"fields": definition_fields}),
            (_("SEO"), {"fields": seo_fields}),
            (_("Gouvernance / Statut"), {"fields": ("is_active", "version", "ia_status", "alerts_pretty", "created_at", "updated_at")}),
            (_("Debug"), {"fields": ("search_text",)}),
        ]

        # Sections spécifiques si variante
        if obj and obj.type == "variante":
            fieldsets.insert(
                3,  # avant SEO
                (_("Explication technique (variante)"), {"fields": [f"explication_technique_{lang}" for lang in ACTIVE_LANGS]}),
            )
            fieldsets.insert(
                3,  # avant Explication
                (_("Procédé (opération/variante)"), {"fields": [f"procede_{lang}" for lang in ACTIVE_LANGS]}),
            )
        else:
            # Pour 'metier' ou 'operation' on garde Processo côté op si tu souhaites
            fieldsets.insert(
                3,  # avant SEO
                (_("Procédé (optionnel)"), {"fields": [f"procede_{lang}" for lang in ACTIVE_LANGS]}),
            )

        return fieldsets

    # ---- Rendus "jolis" pour l'admin ----
    def ia_status(self, obj: GlossaryNode):
        types = [a.get("type") for a in (obj.alerts or []) if isinstance(a, dict)]
        if not types:
            return "🟢 OK"
        if "ia_error" in types:
            return "🔴 Erreur"
        if "ia_pending" in types:
            return "🟡 En attente"
        if "ia_processed" in types:
            return "🟢 Généré"
        return "⚪️ Inconnu"
    ia_status.short_description = _("Statut IA")

    def alerts_pretty(self, obj: GlossaryNode):
        alerts = obj.alerts or []
        if not alerts:
            return "—"
        rows = []
        for a in alerts:
            if not isinstance(a, dict):
                continue
            t = a.get("type", "?")
            d = a.get("detail", "")
            rows.append((format_html("<code>{}</code>", t), d))
        return format_html(
            '<div style="max-width: 860px">{}</div>',
            format_html_join("", "<div>• {} — {}</div>", rows),
        )
    alerts_pretty.short_description = _("Alertes")

    # ---- Actions ----
    @admin.action(description=_("🧠 Lancer l'enrichissement IA (sélection)"))
    def action_trigger_ia(self, request, queryset):
        ids = list(queryset.values_list("glossary_id", flat=True))
        if not ids:
            self.message_user(request, _("Aucun nœud sélectionné."), level=messages.WARNING)
            return
        run_generate_glossary.delay(ids)  # en batch, via glossary_id
        self.message_user(request, _("Enrichissement IA déclenché pour {} nœud(s).").format(len(ids)), level=messages.SUCCESS)

    @admin.action(description=_("🔁 Rebuild FAISS (global)"))
    def action_sync_faiss(self, request, queryset):
        sync_embeddings_to_faiss.delay()
        self.message_user(request, _("Reconstruction FAISS déclenchée."), level=messages.SUCCESS)

    @admin.action(description=_("✅ Marquer comme reviewé (+1 version)"))
    def action_mark_reviewed(self, request, queryset):
        updated = 0
        for obj in queryset:
            obj.reviewed_by = request.user
            obj.version = (obj.version or 1) + 1
            # On ne force pas is_active ici : la règle de clean() prévient les cas non conformes
            obj.save(update_fields=["reviewed_by", "version", "updated_at"])
            updated += 1
        self.message_user(request, _("{} nœud(s) marqués comme reviewés.").format(updated), level=messages.SUCCESS)

# ... Traduction automatique ...
    actions = ("action_translate_wizard", "action_translate_missing", "action_sync_faiss", "action_mark_reviewed")

    @admin.action(description="🌐 Traduire (IA) — assistant")
    def action_translate_wizard(self, request, queryset):
        # 1) première passe : afficher le formulaire
        if "apply" not in request.POST:
            gids = list(queryset.values_list("glossary_id", flat=True))
            if not gids:
                self.message_user(request, "Sélectionne au moins un nœud.", level=messages.WARNING)
                return
            initial_src = get_default_lang()
            # Pré-sélection : toutes les langues sauf la source
            all_codes = list(Language.objects.values_list("code", flat=True))
            initial_targets = [c for c in all_codes if c != initial_src]
            form = TranslateWizardForm(initial={
                "source_lang": initial_src,
                "target_langs": initial_targets,
                "only_missing": True,
                "include_seo": True,
            })
            context = {
                **self.admin_site.each_context(request),
                "opts": self.model._meta,
                "form": form,
                "gids": gids,
                "title": "Assistant de traduction IA",
            }
            return TemplateResponse(request, "admin/glossary/translate_action.html", context)

        # 2) soumission : lancer la tâche
        form = TranslateWizardForm(request.POST)
        if not form.is_valid():
            context = {
                **self.admin_site.each_context(request),
                "opts": self.model._meta,
                "form": form,
                "gids": request.POST.getlist("gids"),
                "title": "Assistant de traduction IA",
            }
            return TemplateResponse(request, "admin/glossary/translate_action.html", context)

        gids = request.POST.getlist("gids")
        src = form.cleaned_data["source_lang"]
        targets = form.cleaned_data["target_langs"]
        only_missing = form.cleaned_data["only_missing"]
        include_seo = form.cleaned_data["include_seo"]

        translate_glossary_nodes.delay(
            gids,
            source_lang=src,
            target_langs=targets,
            only_missing=only_missing,
            include_seo=include_seo,
        )
        self.message_user(
            request,
            f"Traduction IA lancée pour {len(gids)} nœud(s) — source={src}, cibles={', '.join(targets)}.",
            level=messages.SUCCESS,
        )