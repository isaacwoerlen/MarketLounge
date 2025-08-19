# apps/transversales/language/services.py
from __future__ import annotations
import re
from typing import Dict, List, Optional
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.core.cache import cache
from .models import Language, TranslatableKey, Translation
from .utils import get_active_langs, get_default_lang, seo_alerts
from utils_core.utils import compute_checksum, retry_on_exception
from utils_core.validators import normalize_locale, validate_lang
from utils_core.text_cleaning import normalize_text
from utils_core.metrics import record_metric_wrapper, log_metric
from utils_core.alerts import validate_alerts
from utils_core.errors import AlertException
from utils_core.env import get_env_variable
from utils_core.constants import METRIC_LANG_BULK_TRANSLATE_LAT, METRIC_LANG_CACHE_HIT, METRIC_LANG_CACHE_MISS
from transversales.LLM_ai.services import translate_text, LLMError
from verticales.matching.services import encode_text
import logging

logger = logging.getLogger(__name__)

# Config
SEO_MAXLEN = get_env_variable("LANG_SEO_MAXLEN", cast="int", default=160)
BATCH_SIZE = get_env_variable("LANG_BATCH_SIZE", cast="int", default=200)
EMBED_SYNC = get_env_variable("LANG_EMBED_SYNC", cast="bool", default=False)
DEFAULT_PROMPT_TEMPLATE = get_env_variable("LANG_DEFAULT_PROMPT_TEMPLATE", cast="json", default={"tone": "neutral", "max_length": 100})
LLM_TIMEOUT = get_env_variable("LLM_TIMEOUT", cast="float", default=5.0)
LLM_FALLBACK_PROVIDER = get_env_variable("LLM_FALLBACK_PROVIDER", cast="str", default="openai")

def get_active_language(code: str) -> Language:
    """
    Récupère un objet Language actif par code BCP-47.
    Args:
        code (str): Code langue (ex. : 'fr', 'pt-br').
    Returns:
        Language: Objet Language correspondant.
    Raises:
        ValidationError: Si langue inactive ou invalide.
    """
    code = normalize_locale(code)
    validate_lang(code)
    cache_key = f"lang:active:{code}"
    language = cache.get(cache_key)
    if language:
        log_metric(METRIC_LANG_CACHE_HIT, 1, tags={"lang": code})
        return language
    log_metric(METRIC_LANG_CACHE_MISS, 1, tags={"lang": code})
    try:
        language = Language.objects.get(code=code, is_active=True)
        cache.set(cache_key, language, timeout=get_env_variable("LANG_CACHE_TTL", cast="int", default=60))
        return language
    except Language.DoesNotExist:
        raise ValidationError(f"Language {code} is not active", code="invalid_lang")

def validate_seo_lengths(text: str, source_text: str, field: str = "text", max_length: int = SEO_MAXLEN) -> List[Dict]:
    """
    Vérifie la longueur SEO et les placeholders.
    Args:
        text (str): Texte traduit.
        source_text (str): Texte source.
        field (str): Nom du champ (ex. : 'text').
        max_length (int): Longueur maximale.
    Returns:
        List[Dict]: Liste d'alertes [{"type": str, "field": str, "message": str}].
    """
    alerts = seo_alerts(text, field)
    if source_text and field != "keywords":
        src_ph = set(re.findall(r"\{\{.*?\}\}|\{[a-zA-Z0-9_]+\}|%\w|\$\w+", source_text))
        tgt_ph = set(re.findall(r"\{\{.*?\}\}|\{[a-zA-Z0-9_]+\}|%\w|\$\w+", text))
        if src_ph != tgt_ph:
            alerts.append({
                "type": "seo",
                "field": field,
                "message": f"Placeholders mismatch: expected {src_ph}, got {tgt_ph}"
            })
    if len(text) > max_length:
        alerts.append({
            "type": "seo",
            "field": field,
            "message": f"Text exceeds {max_length} characters"
        })
    return validate_alerts(alerts)

@retry_on_exception(exception_types=(LLMError, TimeoutError), max_attempts=3)
def safe_translate_text(
    source_text: str,
    source_lang: str,
    target_lang: str,
    *,
    prompt_template: Optional[Dict] = None,
) -> str:
    """
    Traduit un texte via LLM_ai avec retries.
    Args:
        source_text: Texte source.
        source_lang: Code langue source (BCP-47).
        target_lang: Code langue cible (BCP-47).
        prompt_template: Template pour LLM (optionnel).
    Returns:
        str: Texte traduit.
    Raises:
        LLMError: Si la traduction échoue après retries.
        TimeoutError: Si timeout dépassé.
    """
    source_lang = normalize_locale(source_lang)
    target_lang = normalize_locale(target_lang)
    validate_lang(source_lang)
    validate_lang(target_lang)
    
    normalized_text = normalize_text(source_text, remove_accents_flag=False, lowercase=False)
    prompt = prompt_template or DEFAULT_PROMPT_TEMPLATE
    
    with timeout(LLM_TIMEOUT):
        translated = translate_text(
            text=normalized_text,
            source_lang=source_lang,
            target_lang=target_lang,
            prompt_template=prompt,
        )
    return translated

def tm_lookup(key_id: str, source_checksum: str, target_lang: str, tenant_id: Optional[str] = None) -> Optional[str]:
    """
    Recherche une traduction dans la mémoire de traduction (TM).
    Args:
        key_id: ID de la clé (TranslatableKey).
        source_checksum: Checksum SHA256 du texte source.
        target_lang: Code langue cible (BCP-47).
        tenant_id: ID du tenant (optionnel).
    Returns:
        Optional[str]: Traduction si trouvée, None sinon.
    """
    target_lang = normalize_locale(target_lang)
    validate_lang(target_lang)
    cache_key = f"tm:{source_checksum}:{target_lang}"
    cached = cache.get(cache_key)
    if cached:
        log_metric(METRIC_LANG_CACHE_HIT, 1, tags={"lang": target_lang, "key_id": key_id})
        return cached
    log_metric(METRIC_LANG_CACHE_MISS, 1, tags={"lang": target_lang, "key_id": key_id})
    try:
        translation = Translation.objects.filter(
            key_id=key_id,
            source_checksum=source_checksum,
            lang=target_lang,
            tenant_id=tenant_id
        ).first()
        if translation:
            cache.set(cache_key, translation.text, timeout=get_env_variable("LANG_CACHE_TTL", cast="int", default=60))
            return translation.text
        return None
    except Exception as e:
        logger.error(f"TM lookup failed for {key_id}:{target_lang}: {e}")
        return None

@transaction.atomic
def store_translation(
    key: TranslatableKey,
    target_lang: str,
    translated_text: str,
    source_text: str,
    source_checksum: str,
    origin: str,
    field: str = "text",
    tenant_id: Optional[str] = None,
) -> None:
    """
    Stocke une traduction avec validation.
    """
    target_lang = normalize_locale(target_lang)
    validate_lang(target_lang)
    
    alerts = validate_seo_lengths(translated_text, source_text, field)
    if alerts:
        raise AlertException(
            f"SEO validation failed for {key.scope}:{key.key} ({target_lang})",
            alerts=alerts
        )
    
    try:
        with transaction.atomic():
            Translation.objects.update_or_create(
                key=key,
                lang=target_lang,
                tenant_id=tenant_id,
                defaults={
                    "text": translated_text,
                    "source_checksum": source_checksum,
                    "origin": origin,
                    "alerts": alerts,
                    "version": Translation.objects.filter(
                        key=key, lang=target_lang, tenant_id=tenant_id
                    ).count() + 1
                }
            )
    except IntegrityError as e:
        logger.error(f"Failed to store translation for {key.scope}:{key.key}: {e}")
        raise

@record_metric_wrapper('lang.batch_translate_items', static_tags={'operation': 'items'})
def batch_translate_items(
    item_ids: List[str],
    source_lang: str,
    target_langs: List[str],
    *,
    fields: Optional[List[str]] = None,
    only_missing: bool = True,
    include_seo: bool = True,
    skip_if_target_exists: bool = True,
    tenant_id: Optional[str] = None,
) -> Dict:
    """
    Traduit une liste d'items spécifiques (ex. : glossary IDs).
    Args:
        item_ids: Liste d'IDs d'items à traduire.
        source_lang: Code langue source (BCP-47).
        target_langs: Codes langues cibles (BCP-47).
        fields: Champs à traduire (ex. : ['label', 'definition']).
        only_missing: Traduire uniquement si source absente.
        include_seo: Inclure validation SEO.
        skip_if_target_exists: Ignorer si traduction cible existe.
        tenant_id: ID du tenant.
    Returns:
        Dict: Statistiques du job (processed, per_lang, errors).
    """
    source_lang = normalize_locale(source_lang)
    target_langs = [normalize_locale(lang) for lang in target_langs]
    validate_lang(source_lang)
    for lang in target_langs:
        validate_lang(lang)
    
    if tenant_id:
        validate_tenant_id(tenant_id)
    
    fields = fields or ["text"]
    stats: Dict = {
        "processed": 0,
        "skipped": 0,
        "errors": [],
        "per_lang": {lang: 0 for lang in target_langs},
        "origin_breakdown": {"tm": 0, "llm": 0, "human": 0}
    }
    
    keys = TranslatableKey.objects.filter(id__in=item_ids)
    if tenant_id:
        keys = keys.filter(tenant_id=tenant_id)
    
    for key in keys:
        source_text = key.text
        if not source_text and only_missing:
            stats["skipped"] += len(target_langs)
            continue
        
        source_checksum = compute_checksum(source_text)
        for target_lang in target_langs:
            if skip_if_target_exists:
                exists = Translation.objects.filter(
                    key=key, lang=target_lang, tenant_id=tenant_id
                ).exists()
                if exists:
                    stats["skipped"] += 1
                    stats["per_lang"][target_lang] += 1
                    continue
            
            try:
                cached = tm_lookup(key.id, source_checksum, target_lang, tenant_id)
                if cached:
                    store_translation(
                        key=key,
                        target_lang=target_lang,
                        translated_text=cached,
                        source_text=source_text,
                        source_checksum=source_checksum,
                        origin="tm",
                        field="text",
                        tenant_id=tenant_id,
                    )
                    stats["processed"] += 1
                    stats["per_lang"][target_lang] += 1
                    stats["origin_breakdown"]["tm"] += 1
                    continue
                
                translated = safe_translate_text(
                    source_text=source_text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    prompt_template=getattr(key, "prompt_template", None),
                )
                store_translation(
                    key=key,
                    target_lang=target_lang,
                    translated_text=translated,
                    source_text=source_text,
                    source_checksum=source_checksum,
                    origin="llm",
                    field="text",
                    tenant_id=tenant_id,
                )
                stats["processed"] += 1
                stats["per_lang"][target_lang] += 1
                stats["origin_breakdown"]["llm"] += 1

            except (ValidationError, LLMError, TimeoutError) as e:
                error_msg = f"Translation failed for {key.id}:{target_lang}: {str(e)}"
                stats["errors"].append(error_msg)
                stats["per_lang"][target_lang] += 1
                logger.error(error_msg)

    log_metric(
        METRIC_LANG_BULK_TRANSLATE_LAT,
        stats["processed"],
        tags={"tenant_id": tenant_id or "none", "operation": "items"}
    )
    logger.info(f"Batch items complété: {stats['processed']} traductions, {stats['skipped']} sautés")
    return stats

@record_metric_wrapper('lang.batch_translate', static_tags={'operation': 'scope'})
def batch_translate_scope(
    scope: str,
    source_lang: str,
    target_langs: List[str],
    *,
    tenant_id: Optional[str] = None,
    fields: Optional[List[str]] = None,
    include_seo: bool = True,
    skip_if_target_exists: bool = True,
) -> Dict:
    """
    Traduit un scope entier (ex. : seo:title) vers plusieurs langues.
    """
    try:
        source_lang = normalize_locale(source_lang)
        target_langs = [normalize_locale(lang) for lang in target_langs]
        validate_lang(source_lang)
        for lang in target_langs:
            validate_lang(lang)
        
        if tenant_id:
            validate_tenant_id(tenant_id)
        
        fields = fields or ["text"]
        stats: Dict = {
            "processed": 0,
            "skipped": 0,
            "errors": [],
            "per_lang": {lang: 0 for lang in target_langs},
            "origin_breakdown": {"tm": 0, "llm": 0, "human": 0}
        }
        
        keys = TranslatableKey.objects.filter(Q(scope=scope) | Q(scope__startswith=f"{scope}:"))
        if tenant_id:
            keys = keys.filter(tenant_id=tenant_id)
        
        for key in keys:
            source_text = key.text
            if not source_text:
                stats["skipped"] += len(target_langs)
                continue
            
            source_checksum = compute_checksum(source_text)
            for target_lang in target_langs:
                if skip_if_target_exists:
                    exists = Translation.objects.filter(
                        key=key, lang=target_lang, tenant_id=tenant_id
                    ).exists()
                    if exists:
                        stats["skipped"] += 1
                        stats["per_lang"][target_lang] += 1
                        continue
                
                try:
                    cached = tm_lookup(key.id, source_checksum, target_lang, tenant_id)
                    if cached:
                        store_translation(
                            key=key,
                            target_lang=target_lang,
                            translated_text=cached,
                            source_text=source_text,
                            source_checksum=source_checksum,
                            origin="tm",
                            field="text",
                            tenant_id=tenant_id,
                        )
                        stats["processed"] += 1
                        stats["per_lang"][target_lang] += 1
                        stats["origin_breakdown"]["tm"] += 1
                        continue
                
                    translated = safe_translate_text(
                        source_text=source_text,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        prompt_template=getattr(key, "prompt_template", None),
                    )
                    store_translation(
                        key=key,
                        target_lang=target_lang,
                        translated_text=translated,
                        source_text=source_text,
                        source_checksum=source_checksum,
                        origin="llm",
                        field="text",
                        tenant_id=tenant_id,
                    )
                    stats["processed"] += 1
                    stats["per_lang"][target_lang] += 1
                    stats["origin_breakdown"]["llm"] += 1

                except (ValidationError, LLMError, TimeoutError) as e:
                    error_msg = f"Translation failed for {scope}:{key.key} to {target_lang}: {str(e)}"
                    stats["errors"].append(error_msg)
                    stats["per_lang"][target_lang] += 1
                    logger.error(error_msg)

        logger.info(f"Batch scope complété: {stats['processed']} traductions, {stats['skipped']} sautés")
        return stats

    except ValidationError as e:
        error_msg = f"Batch failed for scope {scope}: {str(e)}"
        stats["errors"].append(error_msg)
        logger.error(error_msg)
        return stats
        