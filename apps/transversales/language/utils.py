# apps/language/utils.py
from __future__ import annotations
from typing import List, Tuple, Optional, Any
from django.conf import settings
from django.core.exceptions import ValidationError
from django.apps import apps
from django.utils.translation import gettext_lazy as _
import logging
import re

logger = logging.getLogger(__name__)

# --- Normalisation ---
def normalize_locale(code: str) -> str:
    """
    Normalise une locale en minuscules avec tiret (ex. : 'PT_BR' -> 'pt-br').
    Valide le format via regex (ex. : 'xx' ou 'xx-yy').
    Args:
        code (str): Code de langue brut (ex. : 'fr', 'PT-BR').
    Returns:
        str: Code normalisé ou vide si invalide.
    """
    if not code:
        logger.warning("Code langue vide fourni")
        return ""
    code = str(code).strip().replace("_", "-")
    parts = [p for p in code.split("-") if p]
    normalized = "-".join(p.lower() for p in parts[:2])
    if not re.match(r"^[a-z]{2}(-[a-z]{2})?$", normalized):
        logger.warning(f"Code langue invalide: '{code}'")
        return ""
    return normalized

def _dedupe_and_normalize(codes: Optional[List[str]]) -> List[str]:
    """
    Déduplique et normalise une liste de codes de langue.
    Args:
        codes (Optional[List[str]]): Liste de codes bruts.
    Returns:
        List[str]: Liste normalisée sans doublons.
    """
    seen, out = set(), []
    for code in codes or []:
        normalized = normalize_locale(code)
        if normalized and normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out

def _fallback_active() -> List[str]:
    """
    Retourne les langues actives par défaut depuis settings.ACTIVE_LANGS.
    Fallback à ['fr', 'en'] si non défini.
    """
    raw = getattr(settings, "ACTIVE_LANGS", ["fr", "en"])
    normalized = _dedupe_and_normalize(raw)
    return normalized or ["fr", "en"]

def _fallback_default() -> str:
    """
    Retourne la langue par défaut depuis settings.DEFAULT_LANG.
    Fallback à 'fr' si non défini.
    """
    return normalize_locale(getattr(settings, "DEFAULT_LANG", "fr")) or "fr"

# --- Accès modèles ---
def _Language():
    """Récupère le modèle Language via apps.get_model."""
    return apps.get_model("language", "Language")

def _TranslatableKey():
    """Récupère le modèle TranslatableKey via apps.get_model."""
    return apps.get_model("language", "TranslatableKey")

def _Translation():
    """Récupère le modèle Translation via apps.get_model."""
    return apps.get_model("language", "Translation")

# --- API publique ---
def get_active_langs() -> List[str]:
    """
    Retourne la liste des langues actives, normalisées.
    Utilise LanguageManager.get_active() avec cache.
    Cache backend: Redis recommandé (via django_redis, settings.CACHES).
    Returns:
        List[str]: Liste des codes langues actives.
    """
    try:
        return _Language().objects.get_active()
    except Exception as e:
        logger.error(f"Erreur récupération langues actives: {str(e)}")
        return _fallback_active()

def get_default_lang() -> str:
    """
    Retourne la langue par défaut, normalisée.
    Utilise LanguageManager.get_default() avec cache.
    Cache backend: Redis recommandé (via django_redis, settings.CACHES).
    Returns:
        str: Code langue par défaut.
    """
    try:
        return _Language().objects.get_default()
    except Exception as e:
        logger.error(f"Erreur récupération langue par défaut: {str(e)}")
        return _fallback_default()

def clear_lang_caches():
    """
    Invalide les caches pour langues actives et par défaut.
    Cache backend: Redis recommandé (via django_redis, settings.CACHES).
    """
    try:
        from django.core.cache import cache
        cache.delete_many([f"language:{suffix}" for suffix in ["active", "default"]])
        logger.debug("Caches langues invalidés")
    except Exception as e:
        logger.error(f"Erreur invalidation caches langues: {str(e)}")

def update_translations(model_instance: Any, scope: str, fields: List[str], tenant_id: Optional[str] = None) -> Any:
    """
    Met à jour les traductions pour un modèle donné dans un scope.
    - Récupère/crée TranslatableKey et Translation.
    - Vérifie checksum pour éviter duplications.
    - Gère tenant_id pour multi-tenancy.
    Args:
        model_instance: Instance du modèle à traduire.
        scope: Scope de traduction (ex. : 'glossary').
        fields: Liste des champs à traduire (ex. : ['label', 'definition']).
        tenant_id: Tenant ID pour isolation.
    Returns:
        Any: Instance mise à jour.
    """
    try:
        TranslatableKey = _TranslatableKey()
        Translation = _Translation()
        translations_to_create, keys_to_update = [], []

        for field in fields:
            source_text = getattr(model_instance, field, "") or ""
            if not source_text:
                continue
            checksum = hashlib.sha256(f"{scope}:{field}".encode()).hexdigest()

            key, _ = TranslatableKey.objects.get_or_create(
                scope=scope,
                key=field,
                tenant_id=tenant_id,
                defaults={"checksum": checksum}
            )
            if key.checksum != checksum:
                key.checksum = checksum
                keys_to_update.append(key)

            default_lang_obj = _Language().objects.get(code=get_default_lang())
            latest = Translation.objects.filter(
                key=key,
                language=default_lang_obj,
                tenant_id=tenant_id
            ).order_by("-version").first()
            if latest and latest.text == source_text:
                continue

            new_translation = Translation(
                key=key,
                language=default_lang_obj,
                text=source_text,
                version=(latest.version + 1) if latest else 1,
                source_checksum=checksum,
                origin="human",
            )
            translations_to_create.append(new_translation)

        if keys_to_update:
            TranslatableKey.objects.bulk_update(keys_to_update, ["checksum", "updated_at"])
            logger.debug(f"{len(keys_to_update)} clés mises à jour pour scope '{scope}'.")
        if translations_to_create:
            Translation.objects.bulk_create(translations_to_create)
            logger.debug(f"{len(translations_to_create)} traductions créées pour scope '{scope}'.")

        return model_instance

    except Exception as e:
        logger.error(f"Erreur mise à jour traductions pour scope {scope}: {str(e)}")
        raise

# --- Validation SEO ---
def seo_alerts(value: str | List[str], field_key: str) -> List[dict]:
    """
    Génère des alertes SEO pour un champ donné.
    Format: [{"type": "seo_length"|"seo_keywords", "field": str, "message": str}]
    Args:
        value: Valeur à valider (str pour title/description, list/str pour keywords).
        field_key (str): Nom du champ (ex. : 'title', 'keywords').
    Returns:
        List[dict]: Liste des alertes SEO.
    """
    title_max = getattr(settings, "SEO_TITLE_MAX", 60)
    desc_max = getattr(settings, "SEO_DESC_MAX", 160)
    kw_max = getattr(settings, "SEO_KEYWORDS_MAX", 10)

    alerts: List[dict] = []
    if field_key == "title" and isinstance(value, str) and len(value) > title_max:
        alerts.append({
            "type": "seo_length",
            "field": "title",
            "message": f"Titre trop long ({len(value)} > {title_max})"
        })
    elif field_key == "description" and isinstance(value, str) and len(value) > desc_max:
        alerts.append({
            "type": "seo_length",
            "field": "description",
            "message": f"Description trop longue ({len(value)} > {desc_max})"
        })
    elif field_key == "keywords":
        if isinstance(value, list):
            keywords = list(dict.fromkeys(value))  # Déduplique
            count = len(keywords)
        elif isinstance(value, str):
            keywords = [k.strip() for k in value.split(",") if k.strip()]  # Trim et ignore vides
            count = len(list(dict.fromkeys(keywords)))  # Déduplique
        else:
            logger.warning(f"Format keywords invalide pour {field_key}: {type(value)}")
            alerts.append({
                "type": "seo_keywords",
                "field": "keywords",
                "message": f"Format invalide (attendu: liste ou chaîne)"
            })
            count = 0
        if count > kw_max:
            alerts.append({
                "type": "seo_keywords",
                "field": "keywords",
                "message": f"Trop de mots-clés ({count} > {kw_max})"
            })
        elif count == 0 and value:
            alerts.append({
                "type": "seo_keywords",
                "field": "keywords",
                "message": "Aucun mot-clé valide"
            })
    if alerts:
        logger.debug(f"Alertes SEO pour {field_key}: {alerts}")
    return alerts