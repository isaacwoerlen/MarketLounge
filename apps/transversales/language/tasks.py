# apps/transversales/language/tasks.py
from celery import shared_task
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Translation, TranslationJob
from .services import batch_translate_scope, batch_translate_items, encode_text
from .serializers import TranslationJobSerializer
from utils_core.validators import normalize_locale, validate_lang, validate_tenant_id
from utils_core.metrics import record_metric_wrapper, log_metric
from utils_core.utils import retry_on_exception
from utils_core.env import get_env_variable
from utils_core.constants import METRIC_LANG_CACHE_HIT, METRIC_LANG_CACHE_MISS
import logging

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    max_retries=3,
    retry_backoff=60,
    retry_jitter=True,
    queue=get_env_variable("CELERY_QUEUE_TRANSLATION", cast="str", default="translation"),
    rate_limit=get_env_variable("CELERY_RATE_LIMIT_TRANSLATION", cast="str", default="100/m")
)
@retry_on_exception(exception_types=(ValidationError, Exception), max_attempts=3)
@record_metric_wrapper('lang.batch_translation_items', static_tags={'operation': 'items'})
def run_batch_translation_items(
    self,
    item_ids: list[str],
    source_lang: str,
    target_langs: list[str],
    fields: list[str] = None,
    only_missing: bool = True,
    include_seo: bool = True,
    skip_if_target_exists: bool = False,
    tenant_id: str = None,
) -> dict:
    """
    Exécute une traduction batch pour des items spécifiques (ex. : glossary IDs).
    - Valide les inputs via TranslationJobSerializer.
    - Appelle batch_translate_items pour traitement.
    - Met à jour TranslationJob (state, stats, errors).
    - Enregistre métriques via metrics app.
    Args:
        item_ids: Liste d'IDs d'items à traduire.
        source_lang: Code de langue source (ex. : 'fr').
        target_langs: Codes des langues cibles (ex. : ['en', 'es']).
        fields: Champs à traduire (ex. : ['label', 'definition']).
        only_missing: Traduire uniquement si source absente.
        include_seo: Inclure champs SEO (description, keywords).
        skip_if_target_exists: Ignorer si traduction cible existe.
        tenant_id: ID du tenant pour multi-tenancy.
    Returns:
        dict: Statistiques du job (processed, per_lang, errors, etc.).
    Raises:
        ValidationError: Si inputs invalides.
    """
    job = None
    try:
        # Normalisation des langues
        source_lang = normalize_locale(source_lang)
        target_langs = [normalize_locale(lang) for lang in target_langs]
        validate_lang(source_lang)
        for lang in target_langs:
            validate_lang(lang)
        
        if tenant_id:
            validate_tenant_id(tenant_id)
        
        # Validation des inputs via serializer
        data = {
            "item_ids": item_ids,
            "source_lang": source_lang,
            "target_langs": target_langs,
            "fields": fields,
            "only_missing": only_missing,
            "include_seo": include_seo,
            "skip_if_target_exists": skip_if_target_exists,
            "tenant_id": tenant_id,
        }
        serializer = TranslationJobSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        
        # Mise à jour job state
        job = TranslationJob.objects.create(
            name=f"batch_items_{timezone.now().isoformat()}",
            state="running",
            source_locale=source_lang,
            target_locales=target_langs,
            scope_filter=[],
            stats={},
            errors=[],
            glossary_ids=[],
            tenant_id=tenant_id,
        )
        stats = batch_translate_items(
            item_ids=item_ids,
            source_lang=source_lang,
            target_langs=target_langs,
            fields=fields,
            only_missing=only_missing,
            include_seo=include_seo,
            skip_if_target_exists=skip_if_target_exists,
            tenant_id=tenant_id,
        )
        job.stats = stats
        job.errors = stats["errors"]
        job.state = "done" if not stats["errors"] else "failed"
        job.save()
        
        log_metric(
            METRIC_LANG_BULK_TRANSLATE_LAT,
            stats["processed"],
            tags={"tenant_id": tenant_id or "none", "operation": "items"}
        )
        logger.info(f"Batch items complété: {stats['processed']} traductions, {stats['skipped']} sautés")
        return stats
    
    except ValidationError as e:
        logger.error(f"Validation échouée pour batch items {item_ids}, tenant={tenant_id or 'none'}: {str(e)}")
        if job:
            job.state = "failed"
            job.errors.append(str(e))
            job.save()
        raise
    except Exception as e:
        logger.error(f"Erreur batch items {item_ids}, tenant={tenant_id or 'none'}: {str(e)}")
        if job:
            job.state = "failed"
            job.errors.append(str(e))
            job.save()
        self.retry(exc=e)

@shared_task(
    bind=True,
    max_retries=3,
    retry_backoff=60,
    retry_jitter=True,
    queue=get_env_variable("CELERY_QUEUE_VECTORIZATION", cast="str", default="vectorization"),
    rate_limit=get_env_variable("CELERY_RATE_LIMIT_VECTORIZATION", cast="str", default="50/m")
)
@retry_on_exception(exception_types=Exception, max_attempts=3)
@record_metric_wrapper('lang.vectorize_translations', static_tags={'operation': 'vectorization'})
def run_vectorize_translations(
    self,
    scopes: list[str],
    tenant_id: str = None,
    lang: str = None,
    only_missing: bool = True,
) -> dict:
    """
    Vectorise les traductions pour un ou plusieurs scopes.
    - Utilise matching.encode_text pour embeddings.
    - Bulk update pour performance.
    Args:
        scopes: Liste de scopes (ex. : ['seo:*', 'glossary']).
        tenant_id: ID du tenant.
        lang: Code langue optionnel (BCP-47).
        only_missing: Vectoriser uniquement si embedding absent.
    Returns:
        dict: Statistiques (vectorized, scopes, errors).
    """
    total = 0
    count = 0
    translations_to_update = []
    try:
        q = Q()
        for s in scopes:
            if s.endswith("*"):
                q |= Q(key__scope__startswith=s[:-1])
            else:
                q |= Q(key__scope=s)
        
        if tenant_id:
            validate_tenant_id(tenant_id)
            q &= Q(tenant_id=tenant_id)
        
        if lang:
            lang = normalize_locale(lang)
            validate_lang(lang)
            q &= Q(lang=lang)
        
        if only_missing:
            q &= Q(embedding__isnull=True)
        
        translations = Translation.objects.filter(q).iterator(chunk_size=100)
        
        for tr in translations:
            total += 1
            try:
                embedding = encode_text(tr.text)
                tr.embedding = embedding
                tr.full_clean()
                translations_to_update.append(tr)
                count += 1
            except Exception as e:
                logger.error(f"Vectorisation échouée pour {tr.key.scope}:{tr.key.key} (id: {tr.id}): {str(e)}")
                log_metric(
                    "language.vectorization_failed",
                    1,
                    tags={
                        "scope": tr.key.scope,
                        "tenant_id": tenant_id or "none",
                        "error": str(e),
                        "translation_id": str(tr.id),
                    }
                )
        
        if translations_to_update:
            Translation.objects.bulk_update(translations_to_update, ["embedding"])
            logger.debug(f"{len(translations_to_update)} traductions vectorisées pour scopes {scopes}, tenant={tenant_id or 'none'}")
        
        log_metric(
            "language.vectorization",
            count,
            tags={
                "scopes": ",".join(scopes),
                "tenant_id": tenant_id or "none",
                "errors": total - count,
            }
        )
        logger.info(f"Vectorisation terminée: {count}/{total} traductions pour scopes {scopes}, tenant={tenant_id or 'none'}")
        return {"vectorized": count, "scopes": scopes, "errors": total - count}
    
    except ValidationError as e:
        logger.error(f"Validation échouée pour vectorisation scopes {scopes}, tenant={tenant_id or 'none'}: {str(e)}")
        log_metric(
            "language.vectorization_failed",
            1,
            tags={"scopes": ",".join(scopes), "tenant_id": tenant_id or "none", "error": str(e)}
        )
        raise
    except Exception as e:
        logger.error(f"Erreur vectorisation scopes {scopes}, tenant={tenant_id or 'none'}: {str(e)}")
        log_metric(
            "language.vectorization_failed",
            1,
            tags={"scopes": ",".join(scopes), "tenant_id": tenant_id or "none", "error": str(e)}
        )
        self.retry(exc=e)