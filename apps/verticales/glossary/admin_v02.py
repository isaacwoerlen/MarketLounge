# apps/glossary/admin.py
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html, format_html_join
from django.db.models.expressions import RawSQL
from django import forms
from django.template.response import TemplateResponse
from .models import GlossaryNode
from .forms import GlossaryNodeForm
from .tasks import run_generate_glossary, sync_embeddings_to_faiss
from language.utils import get_active_langs, get_default_lang
from language.models import Language
from language.tasks import run_glossary_translation_batch


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
        return queryset.extra(
            where=["EXISTS (SELECT 1 FROM jsonb_array_elements(alerts) AS a WHERE a->>'type' = %s)"],
            params=[val],
        )


class MissingLangFilter(SimpleListFilter):
    title = "Incomplet (langue)"
    parameter_name = "missing_lang"

    def lookups(self, request, model_admin):
        return [(c, c.upper()) for c in get_active_langs()]

    def queryset(self, request, qs):
        lang = self.value()
        if not lang:
            return qs
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
    list_display = ("type", "path", "is_active", "version", "reviewed_by", "has_alerts")

    def has_alerts(self, obj):
        return bool(obj.alerts)
    has_alerts.boolean = True

    @admin.action(description=_("🧠 Lancer l'enrichissement IA (sélection)"))
    def action_trigger_ia(self, request, queryset):
        ids = list(queryset.values_list("glossary_id", flat=True))
        if not ids:
            self.message_user(request, _("Aucun nœud sélectionné."), level=messages.WARNING)
            return
        run_generate_glossary.delay(ids)
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
            obj.save(update_fields=["reviewed_by", "version", "updated_at"])
            updated += 1
        self.message_user(request, _("{} nœud(s) marqués comme reviewés.").format(updated), level=messages.SUCCESS)

    @admin.action(description="🌐 Traduire (IA) — assistant")
    def action_translate_wizard(self, request, queryset):
        if "apply" not in request.POST:
            gids = list(queryset.values_list("glossary_id", flat=True))
            if not gids:
                self.message_user(request, "Sélectionne au moins un nœud.", level=messages.WARNING)
                return
            initial_src = get_default_lang()
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

        run_glossary_translation_batch.delay(
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