import pytest
from unittest.mock import patch, Mock
from utils_core.json_utils import safe_json_loads, safe_json_dumps, extract_json_field, stream_json_loads
from utils_core.errors import ValidationError

def test_safe_json_loads_valid():
    """Test safe_json_loads with valid JSON."""
    assert safe_json_loads('{"key": "value"}') == {"key": "value"}
    assert safe_json_loads('[1, 2, 3]') == [1, 2, 3]

def test_safe_json_loads_invalid():
    """Test safe_json_loads with invalid JSON and default."""
    assert safe_json_loads("invalid", default={}) == {}
    assert safe_json_loads("", default=None) is None

def test_safe_json_dumps_valid():
    """Test safe_json_dumps with valid values."""
    assert safe_json_dumps({"key": "value"}) == '{"key": "value"}'
    assert safe_json_dumps([1, 2, 3]) == '[1, 2, 3]'
    assert safe_json_dumps({"key": "é"}, ensure_ascii=False) == '{"key": "é"}'

def test_safe_json_dumps_invalid():
    """Test safe_json_dumps with non-serializable value."""
    with pytest.raises(ValidationError, match="Cannot serialize to JSON"):
        safe_json_dumps(lambda x: x)

def test_extract_json_field_valid():
    """Test extract_json_field with valid paths."""
    value = {"key1": {"key2": [{"field": "value"}]}}
    assert extract_json_field(value, "key1.key2[0].field") == "value"
    assert extract_json_field(value, "key1.key2[0]") == {"field": "value"}

def test_extract_json_field_invalid_path():
    """Test extract_json_field with invalid paths."""
    value = {"key1": {"key2": [1, 2]}}
    assert extract_json_field(value, "key1.invalid", default="missing") == "missing"
    assert extract_json_field(value, "key1.key2[2]", default=None) is None

@patch("utils_core.json_utils.ijson", None)
def test_stream_json_loads_without_ijson_array():
    """Test stream_json_loads with array JSON and no ijson."""
    data = '[{"id": 1}, {"id": 2}]'
    result = list(stream_json_loads(data))
    assert result == [{"id": 1}, {"id": 2}]

@patch("utils_core.json_utils.ijson", None)
def test_stream_json_loads_without_ijson_object():
    """Test stream_json_loads with object JSON and no ijson."""
    data = '{"key": "value"}'
    result = list(stream_json_loads(data))
    assert result == [{"key": "value"}]

@patch("utils_core.json_utils.ijson", None)
def test_stream_json_loads_without_ijson_invalid():
    """Test stream_json_loads with invalid JSON and no ijson."""
    with pytest.raises(ValidationError, match="Invalid JSON for streaming"):
        list(stream_json_loads("invalid"))

@patch("utils_core.json_utils.ijson", None)
def test_stream_json_loads_without_ijson_unsupported_type():
    """Test stream_json_loads with unsupported type and no ijson."""
    with pytest.raises(ValidationError, match="Streaming only supports JSON arrays or objects"):
        list(stream_json_loads('"string"'))

@patch("utils_core.json_utils.ijson")
def test_stream_json_loads_with_ijson(mock_ijson):
    """Test stream_json_loads with ijson."""
    mock_parser = Mock()
    mock_parser.return_value = [
        ("", "start_array", None),
        ("item", "start_map", None),
        ("item.id", "number", 1),
        ("item", "end_map", {"id": 1}),
        ("item", "start_map", None),
        ("item.id", "number", 2),
        ("item", "end_map", {"id": 2}),
        ("", "end_array", None),
    ]
    mock_ijson.parse = mock_parser
    data = '[{"id": 1}, {"id": 2}]'
    result = list(stream_json_loads(data))
    assert result == [{"id": 1}, {"id": 2}]

@patch("utils_core.json_utils.ijson")
def test_stream_json_loads_with_ijson_error(mock_ijson):
    """Test stream_json_loads with ijson parsing error."""
    mock_ijson.parse.side_effect = Exception("Invalid JSON")
    with pytest.raises(ValidationError, match="Invalid JSON for streaming"):
        list(stream_json_loads("invalid"))