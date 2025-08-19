# apps/transversales/language/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.conf import settings
from .models import Language, Translation
from .utils import clear_lang_caches
from .tasks import run_vectorize_scopes
from transversales.metrics.services import record_metric
import logging

logger = logging.getLogger(__name__)

@receiver([post_save, post_delete], sender=Language)
def clear_language_caches(sender, instance, **kwargs):
    """
    Invalide les caches pour langues actives/défaut après modification/suppression.
    - Appelé sur post_save/post_delete de Language.
    - Enregistre métrique pour suivi.
    Args:
        sender: Classe du modèle (Language).
        instance: Instance de Language modifiée/supprimée.
        kwargs: Arguments supplémentaires du signal.
    """
    try:
        clear_lang_caches()
        action = "save" if kwargs.get("created") is not None else "delete"
        record_metric(
            name="language.cache_invalidation",
            value=1,
            tags={
                "model": "Language",
                "action": action,
                "code": instance.code,
                "instance_id": str(instance.id),
            }
        )
        logger.info(f"Caches langues invalidés pour {instance.code} (action: {action}, id: {instance.id})")
    except Exception as e:
        logger.error(f"Erreur invalidation caches langues pour {instance.code} (id: {instance.id}): {str(e)}")
        record_metric(
            name="language.signal_error",
            value=1,
            tags={
                "model": "Language",
                "action": action,
                "error": str(e),
                "instance_id": str(instance.id),
            }
        )

@receiver(post_save, sender=Translation)
def vectorize_translation(sender, instance, created, **kwargs):
    """
    Gère post_save de Translation.
    - Invalide le cache TM pour la traduction.
    - Déclenche vectorisation asynchrone si LANG_EMBED_SYNC=False et texte non vide.
    - Enregistre métrique pour suivi.
    Args:
        sender: Classe du modèle (Translation).
        instance: Instance de Translation sauvegardée.
        created: Booléen indiquant si nouvelle instance.
        kwargs: Arguments supplémentaires du signal.
    """
    try:
        # Invalidation cache TM
        cache_key = f"tm:{instance.key.id}:{instance.source_checksum}:{instance.language.code}"
        cache.delete(cache_key)
        record_metric(
            name="language.tm_cache_invalidation",
            value=1,
            tags={
                "scope": instance.key.scope,
                "language": instance.language.code,
                "tenant_id": instance.key.tenant_id or "none",
                "instance_id": str(instance.id),
            }
        )
        logger.debug(f"Cache TM invalidé: {cache_key} (id: {instance.id})")

        # Vectorisation asynchrone si texte non vide
        if not getattr(settings, "LANG_EMBED_SYNC", False) and instance.text and instance.text.strip():
            task = run_vectorize_scopes.delay([instance.key.scope], instance.key.tenant_id)
            record_metric(
                name="language.vectorization_triggered",
                value=1,
                tags={
                    "scope": instance.key.scope,
                    "language": instance.language.code,
                    "tenant_id": instance.key.tenant_id or "none",
                    "task_id": task.id,
                    "instance_id": str(instance.id),
                }
            )
            logger.info(f"Vectorisation asynchrone déclenchée pour scope: {instance.key.scope}, Task ID: {task.id}, Translation ID: {instance.id}")

    except Exception as e:
        scope_key = f"{instance.key.scope}:{instance.key.key}" if instance.key else "unknown"
        logger.error(f"Erreur signal Translation pour {scope_key} (id: {instance.id}): {str(e)}")
        record_metric(
            name="language.signal_error",
            value=1,
            tags={
                "model": "Translation",
                "scope": scope_key,
                "action": "save",
                "error": str(e),
                "instance_id": str(instance.id),
            }
        )