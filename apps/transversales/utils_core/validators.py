from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from utils_core.constants import (
    TENANT_PATTERN, LANG_BCP47_PATTERN, SHA256_HEX_PATTERN, SCOPE_PATTERN,
    ERR_INVALID_TENANT, ERR_INVALID_LANG, ERR_INVALID_CHECKSUM, ERR_INVALID_SCOPE,
    DEFAULT_JSON_MAX_BYTES, ERR_JSON_TOO_LARGE, ERR_JSON_INVALID_TYPE
)
import re
import json

# Regex constants for validation
TENANT_RE = re.compile(TENANT_PATTERN)
LANG_BCP47_RE = re.compile(LANG_BCP47_PATTERN)
SHA256_HEX_RE = re.compile(SHA256_HEX_PATTERN)
SCOPE_RE = re.compile(SCOPE_PATTERN)

__all__ = [
    "validate_tenant_id",
    "validate_lang",
    "normalize_locale",
    "validate_checksum",
    "validate_scope",
    "validate_json_field",
]

def validate_tenant_id(value):
    """Validate tenant_id format (e.g., tenant_123)."""
    if value and not TENANT_RE.match(value):
        raise ValidationError(
            _("Tenant_id must match pattern 'tenant_[a-zA-Z0-9_]+'"),
            code=ERR_INVALID_TENANT
        )

def validate_lang(value):
    """Validate language code format against BCP-47 (e.g., fr, pt-br)."""
    if value and not LANG_BCP47_RE.match(value):
        raise ValidationError(
            _("Language code must match BCP-47 (e.g., fr, pt-br)"),
            code=ERR_INVALID_LANG
        )

def normalize_locale(value: str | None) -> str | None:
    """
    Normalize a language code to BCP-47 format (lowercase, hyphen-separated).
    - Converts to lowercase and replaces underscores with hyphens.
    - Utilisé dans language (Translation.source_locale), matching (query language),
      LLM_ai (prompt localization), et curation (validation multilingue).

    Args:
        value (str | None): Language code to normalize (e.g., 'FR', 'pt_br').

    Returns:
        str | None: Normalized code (e.g., 'fr', 'pt-br') or None if input is None.

    Examples:
        >>> from utils_core.validators import normalize_locale
        >>> normalize_locale('pt_BR')  # language: Translation.source_locale
        'pt-br'
        >>> normalize_locale('FR')  # matching: query lang
        'fr'
        >>> normalize_locale(None)  # curation: validation
        None
    """
    if value is None:
        return None
    return value.lower().replace('_', '-')

def validate_checksum(value):
    """Validate SHA256 hex checksum (64 lowercase hex chars)."""
    if value and not SHA256_HEX_RE.match(value):
        raise ValidationError(
            _("Checksum must be a 64-char lowercase SHA256 hex"),
            code=ERR_INVALID_CHECKSUM
        )

def validate_scope(value):
    """Validate scope format (e.g., glossary, seo:title)."""
    if value and not SCOPE_RE.match(value):
        raise ValidationError(
            _("Scope must be alphanumeric with underscores or hierarchical (e.g., glossary, seo:title)"),
            code=ERR_INVALID_SCOPE
        )

def validate_json_field(value, max_size_bytes=DEFAULT_JSON_MAX_BYTES):
    """
    Validate JSONField content (list or dict, max size in bytes).
    Used for payload, alerts, provider_info, target_locales, etc.
    """
    if value is None:
        return
    if not isinstance(value, (dict, list)):
        raise ValidationError(
            _("JSONField must be a dict or list"),
            code=ERR_JSON_INVALID_TYPE
        )
    size = len(json.dumps(value).encode('utf-8'))
    if size > max_size_bytes:
        raise ValidationError(
            _("JSONField size exceeds %(kb)sKB limit") % {"kb": max_size_bytes/1024},
            code=ERR_JSON_TOO_LARGE
        )
        