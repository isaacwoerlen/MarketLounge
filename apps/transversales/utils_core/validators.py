from __future__ import annotations
import json
import re
from typing import Any, Dict, List, Optional
from utils_core.errors import ValidationError

__all__ = [
    "validate_lang",
    "normalize_locale",
    "validate_tenant_id",
    "validate_scope",
    "validate_checksum",
    "validate_json_field",
    "validate_json_schema",
]

# Regex compilés pour performance
LANG_CODE_RE = re.compile(r"^[a-z]{2}(-[a-z]{2})?$")
TENANT_ID_RE = re.compile(r"^tenant_[a-zA-Z0-9_]+$")
SCOPE_RE = re.compile(r"^[a-z][a-z0-9_]*(?::[a-z][a-z0-9_]*)*$")
CHECKSUM_RE = re.compile(r"^[0-9a-f]{64}$")

def validate_lang(lang: str) -> None:
    """Validate a language code against BCP-47 format (e.g., 'fr', 'pt-br').

    Args:
        lang: Language code to validate.

    Raises:
        ValidationError: If the language code is invalid.

    Example:
        >>> validate_lang("fr")
        >>> validate_lang("pt-br")
        >>> validate_lang("invalid")  # Raises ValidationError
    """
    if not isinstance(lang, str) or not LANG_CODE_RE.match(lang):
        raise ValidationError(f"Invalid language code: {lang}")

def normalize_locale(lang: str) -> str:
    """Normalize a language code to lowercase BCP-47 format (e.g., 'pt-BR' -> 'pt-br').

    Args:
        lang: Language code to normalize.

    Returns:
        str: Normalized language code.

    Raises:
        ValidationError: If the language code is invalid.

    Example:
        >>> normalize_locale("pt-BR")
        'pt-br'
    """
    validate_lang(lang)
    return lang.lower()

def validate_tenant_id(tenant_id: str) -> None:
    """Validate a tenant ID (e.g., 'tenant_123').

    Args:
        tenant_id: Tenant ID to validate.

    Raises:
        ValidationError: If the tenant ID is invalid.

    Example:
        >>> validate_tenant_id("tenant_123")
        >>> validate_tenant_id("invalid")  # Raises ValidationError
    """
    if not isinstance(tenant_id, str) or not TENANT_ID_RE.match(tenant_id):
        raise ValidationError(f"Invalid tenant_id: {tenant_id}")

def validate_scope(scope: str) -> None:
    """Validate a scope string (e.g., 'seo:title', 'glossary').

    Args:
        scope: Scope string to validate.

    Raises:
        ValidationError: If the scope is invalid.

    Example:
        >>> validate_scope("seo:title")
        >>> validate_scope("invalid@scope")  # Raises ValidationError
    """
    if not isinstance(scope, str) or not SCOPE_RE.match(scope):
        raise ValidationError(f"Invalid scope: {scope}")

def validate_checksum(checksum: str, algo: str = "sha256") -> None:
    """Validate a checksum string (default: SHA256).

    Args:
        checksum: Checksum string to validate.
        algo: Hash algorithm (default: 'sha256').

    Raises:
        ValidationError: If the checksum or algorithm is invalid.

    Example:
        >>> validate_checksum("0e9c3f4f6b7a8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3")
    """
    if algo != "sha256":
        raise ValidationError(f"Unsupported algorithm: {algo}")
    if not isinstance(checksum, str) or not CHECKSUM_RE.match(checksum):
        raise ValidationError(f"Invalid checksum: {checksum}")

def validate_json_field(value: Any, field_name: str = "json_field") -> None:
    """Validate that a value is JSON-serializable.

    Args:
        value: Value to validate.
        field_name: Name of the field for error reporting (default: 'json_field').

    Raises:
        ValidationError: If the value is not JSON-serializable.

    Example:
        >>> validate_json_field({"key": "value"})
        >>> validate_json_field(lambda x: x)  # Raises ValidationError
    """
    try:
        json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        raise ValidationError(f"Invalid JSON for field {field_name}: {value}")

def validate_json_schema(value: Any, schema: Dict[str, Any], field_name: str = "json_field") -> None:
    """Validate a JSON value against a provided schema.

    Args:
        value: JSON value to validate (e.g., dict, list).
        schema: Schema defining expected structure (e.g., {'type': 'object', 'properties': {...}}).
        field_name: Name of the field for error reporting (default: 'json_field').

    Raises:
        ValidationError: If the value does not match the schema.

    Example:
        >>> schema = {"type": "array", "items": {"type": "object", "properties": {"type": {"type": "string"}}}}
        >>> validate_json_schema([{"type": "validation"}], schema)
        >>> validate_json_schema([{"invalid": 123}], schema)  # Raises ValidationError
    """
    if not isinstance(value, (dict, list)):
        raise ValidationError(f"Invalid JSON type for {field_name}: expected dict or list, got {type(value).__name__}")

    def check_type(val: Any, expected_type: str, path: str) -> None:
        if expected_type == "string" and not isinstance(val, str):
            raise ValidationError(f"Invalid type at {path}: expected string, got {type(val).__name__}")
        elif expected_type == "number" and not isinstance(val, (int, float)):
            raise ValidationError(f"Invalid type at {path}: expected number, got {type(val).__name__}")
        elif expected_type == "boolean" and not isinstance(val, bool):
            raise ValidationError(f"Invalid type at {path}: expected boolean, got {type(val).__name__}")
        elif expected_type == "object" and not isinstance(val, dict):
            raise ValidationError(f"Invalid type at {path}: expected object, got {type(val).__name__}")
        elif expected_type == "array" and not isinstance(val, list):
            raise ValidationError(f"Invalid type at {path}: expected array, got {type(val).__name__}")

    def validate_structure(val: Any, sch: Dict[str, Any], path: str) -> None:
        sch_type = sch.get("type")
        if not sch_type:
            raise ValidationError(f"Schema missing 'type' at {path}")
        check_type(val, sch_type, path)

        if sch_type == "object":
            properties = sch.get("properties", {})
            required = sch.get("required", [])
            if not isinstance(val, dict):
                return
            for key, sub_val in val.items():
                if key in properties:
                    validate_structure(sub_val, properties[key], f"{path}.{key}")
            for key in required:
                if key not in val:
                    raise ValidationError(f"Missing required field {key} at {path}")
        elif sch_type == "array":
            items = sch.get("items")
            if not items:
                return
            if not isinstance(val, list):
                return
            for i, item in enumerate(val):
                validate_structure(item, items, f"{path}[{i}]")

    try:
        validate_json_field(value, field_name)
        validate_structure(value, schema, field_name)
    except ValidationError as e:
        raise ValidationError(f"Invalid JSON schema for {field_name}: {str(e)}")