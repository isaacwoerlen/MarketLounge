import pytest
from utils_core.validators import (
    validate_lang,
    normalize_locale,
    validate_tenant_id,
    validate_scope,
    validate_checksum,
    validate_json_field,
    validate_json_schema,
)
from utils_core.errors import ValidationError

def test_validate_lang_valid():
    """Test validate_lang with valid language codes."""
    validate_lang("fr")
    validate_lang("pt-br")
    assert True  # No exception raised

def test_validate_lang_invalid():
    """Test validate_lang with invalid language codes."""
    with pytest.raises(ValidationError, match="Invalid language code"):
        validate_lang("invalid")
    with pytest.raises(ValidationError, match="Invalid language code"):
        validate_lang("fr-FR-123")

def test_normalize_locale_valid():
    """Test normalize_locale with valid inputs."""
    assert normalize_locale("fr") == "fr"
    assert normalize_locale("pt-BR") == "pt-br"

def test_normalize_locale_invalid():
    """Test normalize_locale with invalid inputs."""
    with pytest.raises(ValidationError, match="Invalid language code"):
        normalize_locale("invalid")

def test_validate_tenant_id_valid():
    """Test validate_tenant_id with valid tenant IDs."""
    validate_tenant_id("tenant_123")
    validate_tenant_id("tenant_abc_456")
    assert True

def test_validate_tenant_id_invalid():
    """Test validate_tenant_id with invalid tenant IDs."""
    with pytest.raises(ValidationError, match="Invalid tenant_id"):
        validate_tenant_id("invalid@tenant")
    with pytest.raises(ValidationError, match="Invalid tenant_id"):
        validate_tenant_id("")

def test_validate_scope_valid():
    """Test validate_scope with valid scopes."""
    validate_scope("seo:title")
    validate_scope("glossary")
    validate_scope("company:profile")
    assert True

def test_validate_scope_invalid():
    """Test validate_scope with invalid scopes."""
    with pytest.raises(ValidationError, match="Invalid scope"):
        validate_scope("invalid@scope")
    with pytest.raises(ValidationError, match="Invalid scope"):
        validate_scope(":invalid")

def test_validate_checksum_valid():
    """Test validate_checksum with valid SHA256 checksum."""
    checksum = "0e9c3f4f6b7a8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3"
    validate_checksum(checksum)
    assert True

def test_validate_checksum_invalid():
    """Test validate_checksum with invalid checksum or algorithm."""
    with pytest.raises(ValidationError, match="Invalid checksum"):
        validate_checksum("invalid")
    with pytest.raises(ValidationError, match="Unsupported algorithm"):
        validate_checksum("0e9c3f4f6b7a8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3", algo="md5")

def test_validate_json_field_valid():
    """Test validate_json_field with JSON-serializable values."""
    validate_json_field({"key": "value"})
    validate_json_field([1, 2, 3])
    validate_json_field("string")
    assert True

def test_validate_json_field_invalid():
    """Test validate_json_field with non-serializable values."""
    with pytest.raises(ValidationError, match="Invalid JSON for field json_field"):
        validate_json_field(lambda x: x)

def test_validate_json_schema_valid_array():
    """Test validate_json_schema with valid array schema."""
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "field": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["type", "message"],
        },
    }
    value = [{"type": "validation", "field": "concept", "message": "Invalid"}]
    validate_json_schema(value, schema, "alerts")
    assert True

def test_validate_json_schema_valid_object():
    """Test validate_json_schema with valid object schema."""
    schema = {
        "type": "object",
        "properties": {
            "tenant_id": {"type": "string"},
            "scope": {"type": "string"},
        },
        "required": ["tenant_id"],
    }
    value = {"tenant_id": "tenant_123", "scope": "company"}
    validate_json_schema(value, schema, "payload")
    assert True

def test_validate_json_schema_invalid_type():
    """Test validate_json_schema with invalid type."""
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    with pytest.raises(ValidationError, match="Invalid type at payload: expected object"):
        validate_json_schema([1, 2, 3], schema, "payload")

def test_validate_json_schema_missing_required():
    """Test validate_json_schema with missing required field."""
    schema = {
        "type": "object",
        "properties": {"tenant_id": {"type": "string"}},
        "required": ["tenant_id"],
    }
    with pytest.raises(ValidationError, match="Missing required field tenant_id"):
        validate_json_schema({"scope": "company"}, schema, "payload")

def test_validate_json_schema_invalid_property_type():
    """Test validate_json_schema with invalid property type."""
    schema = {
        "type": "array",
        "items": {"type": "object", "properties": {"type": {"type": "string"}}},
    }
    with pytest.raises(ValidationError, match="Invalid type at alerts\\[0\\].type: expected string"):
        validate_json_schema([{"type": 123}], schema, "alerts")

def test_validate_json_schema_invalid_json():
    """Test validate_json_schema with non-JSON-serializable value."""
    schema = {"type": "object", "properties": {"data": {"type": "string"}}}
    with pytest.raises(ValidationError, match="Invalid JSON for field data"):
        validate_json_schema(lambda x: x, schema, "data")