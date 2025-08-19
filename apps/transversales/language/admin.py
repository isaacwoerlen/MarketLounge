# apps/transversales/language/admin.py
from django.contrib import admin, messages
from django.http import HttpResponse, StreamingHttpResponse
from django.utils.translation import gettext_lazy as _
from django.urls import path
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from .models import Language, Translation, TranslatableKey, TranslationJob
from .utils import clear_lang_caches
from .permissions import (
    can_view_language,
    can_change_language,
    can_delete_language,
    can_view_translatable_key,
    can_change_translatable_key,
    can_view_translation,
    can_change_translation,
    can_view_translation_job,
    can_rerun_translation_job,
    can_export_translation_job,
)
from .tasks import run_batch_translation_items, run_batch_translation_scope, run_vectorize_scopes
import logging
import csv
import bleach

logger = logging.getLogger(__name__)

# Config pour sanitisation XSS
BLEACH_ALLOWED_TAGS = ['p', 'b', 'i', 'u', 'em', 'strong', 'a']
BLEACH_ALLOWED_ATTRIBUTES = {'a': ['href', 'title']}

class LanguagePermissionMixin:
    """
    Mixin pour permissions Language (view, change, delete).
    Utilise permissions.py pour checks granulaires.
    """
    def has_view_permission(self, request, obj=None):
        """Vérifie si l'utilisateur peut voir un objet Language."""
        return can_view_language(request.user, obj)

    def has_change_permission(self, request, obj=None):
        """Vérifie si l'utilisateur peut modifier un objet Language."""
        return can_change_language(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        """Vérifie si l'utilisateur peut supprimer un objet Language."""
        return can_delete_language(request.user, obj)

@admin.register(Language)
class LanguageAdmin(LanguagePermissionMixin, admin.ModelAdmin):
    """
    Admin pour Language.
    - Affiche: code, name, is_active, is_default.
    - Filtres: is_active, is_default.
    - Recherche: code, name.
    - Actions: activate, deactivate.
    - Pagination: 100 par page.
    """
    list_display = ("code", "name", "is_active", "is_default", "priority")
    list_filter = ("is_active", "is_default")
    search_fields = ("code", "name")
    actions = ["activate", "deactivate"]
    ordering = ("priority", "code")
    list_per_page = 100  # Pagination pour gros volumes

    class Media:
        css = {"all": ("language/language_admin.css",)}
        js = ("language/language_admin.js",)

    def activate(self, request, queryset):
        """
        Active les langues sélectionnées et invalide les caches.
        """
        try:
            count = queryset.update(is_active=True)
            clear_lang_caches()
            messages.success(request, _("%d langues activées.") % count)
            logger.info(f"{count} langues activées par {request.user.username}")
        except Exception as e:
            logger.error(f"Erreur activation langues: {str(e)}")
            messages.error(request, _("Erreur lors de l'activation: %s") % str(e))

    def deactivate(self, request, queryset):
        """
        Désactive les langues sélectionnées (sauf langue par défaut).
        """
        try:
            count = queryset.exclude(is_default=True).update(is_active=False)
            clear_lang_caches()
            messages.success(request, _("%d langues désactivées.") % count)
            logger.info(f"{count} langues désactivées par {request.user.username}")
        except Exception as e:
            logger.error(f"Erreur désactivation langues: {str(e)}")
            messages.error(request, _("Erreur lors de la désactivation: %s") % str(e))

@admin.register(TranslatableKey)
class TranslatableKeyAdmin(admin.ModelAdmin):
    """
    Admin pour TranslatableKey.
    - Affiche: scope, key, tenant_id.
    - Filtres: scope, tenant_id.
    - Recherche: scope, key.
    - Pagination: 100 par page.
    """
    list_display = ("scope", "key", "tenant_id")
    list_filter = ("scope", "tenant_id")
    search_fields = ("scope", "key")
    list_per_page = 100

    def has_view_permission(self, request, obj=None):
        return can_view_translatable_key(request.user, obj)

    def has_change_permission(self, request, obj=None):
        return can_change_translatable_key(request.user, obj)

@admin.register(Translation)
class TranslationAdmin(admin.ModelAdmin):
    """
    Admin pour Translation.
    - Affiche: key, language, short_text, origin.
    - Filtres: language, origin, tenant_id.
    - Recherche: text, key__scope, key__key.
    - Pagination: 100 par page.
    """
    list_display = ("key", "language", "short_text", "origin")
    list_filter = ("language__code", "origin", "tenant_id")
    search_fields = ("text", "key__scope", "key__key")
    list_per_page = 100

    def short_text(self, obj):
        """Affiche un extrait sécurisé du texte traduit."""
        text = (obj.text or "")[:50]
        return bleach.clean(text, tags=BLEACH_ALLOWED_TAGS, attributes=BLEACH_ALLOWED_ATTRIBUTES)
    short_text.short_description = _("Text")
    short_text.admin_order_field = "text"

    def has_view_permission(self, request, obj=None):
        return can_view_translation(request.user, obj)

    def has_change_permission(self, request, obj=None):
        return can_change_translation(request.user, obj)

@admin.register(TranslationJob)
class TranslationJobAdmin(admin.ModelAdmin):
    """
    Admin pour TranslationJob.
    - Affiche: name, state, source_locale, created_at.
    - Filtres: state, source_locale, tenant_id.
    - Actions: rerun_job, export_results, vectorize_job.
    - Pagination: 100 par page.
    """
    list_display = ("name", "state", "source_locale", "created_at")
    list_filter = ("state", "source_locale", "tenant_id")
    actions = ["rerun_job", "export_results", "vectorize_job"]
    list_per_page = 100
    change_form_template = "admin/language/translation_job.html"

    def get_urls(self):
        """Ajoute URLs personnalisées pour actions."""
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/rerun/",
                self.admin_site.admin_view(self.rerun_job),
                name="language_translationjob_rerun",
            ),
            path(
                "<path:object_id>/export/",
                self.admin_site.admin_view(self.export_results),
                name="language_translationjob_export",
            ),
        ]
        return custom_urls + urls

    def has_view_permission(self, request, obj=None):
        return can_view_translation_job(request.user, obj)

    def has_change_permission(self, request, obj=None):
        return can_rerun_translation_job(request.user, obj)

    @require_POST
    @csrf_protect
    def rerun_job(self, request, object_id):
        """
        Relance un job de traduction via Celery.
        - Vérifie méthode POST, permissions.
        - Redirige vers change page après action.
        """
        try:
            job = self.get_object(request, object_id)
            if not job:
                logger.error(f"Job {object_id} non trouvé pour relance par {request.user.username}")
                messages.error(request, _("Job non trouvé."))
                return HttpResponse(status=404)
            if not can_rerun_translation_job(request.user, job):
                logger.error(f"Permission refusée pour relance job {object_id} par {request.user.username}")
                messages.error(request, _("Permission refusée."))
                return HttpResponse(status=403)

            task = run_batch_translation_items.delay(
                item_ids=job.glossary_ids,
                source_lang=job.source_locale,
                target_langs=job.target_locales,
                tenant_id=job.tenant_id,
            )
            messages.success(request, _("Job %s relancé (Task ID: %s).") % (object_id, task.id))
            logger.info(f"Job {object_id} relancé par {request.user.username}, Task ID: {task.id}")
            return redirect(f"../../{object_id}/change/")

        except Exception as e:
            logger.error(f"Erreur relance job {object_id}: {str(e)}")
            messages.error(request, _("Erreur relance: %s") % str(e))
            return redirect(f"../../{object_id}/change/")

    @require_POST
    @csrf_protect
    def export_results(self, request, object_id):
        """
        Exporte les résultats d'un job en CSV.
        - Vérifie méthode POST, permissions.
        - Utilise StreamingHttpResponse pour gros volumes.
        """
        try:
            job = self.get_object(request, object_id)
            if not job:
                logger.error(f"Job {object_id} non trouvé pour export par {request.user.username}")
                messages.error(request, _("Job non trouvé."))
                return HttpResponse(status=404)
            if not can_export_translation_job(request.user, job):
                logger.error(f"Permission refusée pour export job {object_id} par {request.user.username}")
                messages.error(request, _("Permission refusée."))
                return HttpResponse(status=403)

            def csv_stream():
                writer = csv.writer()
                yield writer.writerow(["Locale", "Translated", "Errors"])
                for locale, count in (job.stats.get("per_lang", {}) or {}).items():
                    yield writer.writerow([locale, count, "; ".join(job.errors.get(locale, []) or [])])

            response = StreamingHttpResponse(
                csv_stream(),
                content_type="text/csv; charset=utf-8"
            )
            response["Content-Disposition"] = f'attachment; filename="job_{object_id}_results.csv"'
            logger.info(f"Export CSV job {object_id} par {request.user.username}")
            return response

        except Exception as e:
            logger.error(f"Erreur export job {object_id}: {str(e)}")
            messages.error(request, _("Erreur export: %s") % str(e))
            return redirect(f"../../{object_id}/change/")

    def vectorize_job(self, request, queryset):
        """
        Déclenche la vectorisation asynchrone des traductions pour les jobs sélectionnés.
        - Vérifie permissions et lance via Celery.
        - Envoie message avec task IDs.
        """
        try:
            task_ids = []
            for job in queryset:
                if not can_rerun_translation_job(request.user, job):
                    logger.error(f"Permission refusée pour vectorisation job {job.id} par {request.user.username}")
                    messages.error(request, _("Permission refusée pour job %s.") % job.id)
                    continue
                task = run_vectorize_scopes.delay(job.scope_filter, job.tenant_id)
                task_ids.append(task.id)
                logger.info(f"Vectorisation job {job.id} lancée par {request.user.username}, Task ID: {task.id}")
            if task_ids:
                messages.success(request, _("Vectorisation lancée pour %d jobs (Task IDs: %s).") % (len(task_ids), ", ".join(task_ids)))
            else:
                messages.warning(request, _("Aucun job vectorisé (vérifiez permissions)."))
        except Exception as e:
            logger.error(f"Erreur vectorisation jobs: {str(e)}")
            messages.error(request, _("Erreur vectorisation: %s") % str(e))

    vectorize_job.short_description = _("Vectorize selected jobs")
    vectorize_job.aria_label = _("Trigger vectorization for selected translation jobs")

    def clear_tm_cache(self, request, queryset):
        """
        Invalide le cache Translation Memory pour les jobs sélectionnés.
        """
        try:
            from django.core.cache import cache
            count = 0
            for job in queryset:
                keys = [f"tm:{key_id}:{source_checksum}:{lang}"
                        for key_id in job.stats.get("keys_processed", [])
                        for source_checksum in job.stats.get("source_checksums", [])
                        for lang in job.target_locales]
                cache.delete_many(keys)
                count += len(keys)
            messages.success(request, _("%d clés de cache TM invalidées.") % count)
            logger.info(f"{count} clés TM invalidées pour {queryset.count()} jobs par {request.user.username}")
        except Exception as e:
            logger.error(f"Erreur invalidation cache TM: {str(e)}")
            messages.error(request, _("Erreur invalidation cache: %s") % str(e))
