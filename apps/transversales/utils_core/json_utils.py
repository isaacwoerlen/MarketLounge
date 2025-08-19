from __future__ import annotations
import json
from typing import Any, Optional, Iterator
from utils_core.errors import ValidationError

try:
    import ijson  # type: ignore
except ImportError:
    ijson = None

__all__ = ["safe_json_loads", "safe_json_dumps", "extract_json_field", "stream_json_loads"]

def safe_json_loads(data: str, default: Any = None) -> Any:
    """Parse a JSON string, returning a default value on failure.

    Args:
        data: JSON string to parse.
        default: Value to return if parsing fails (default: None).

    Returns:
        Any: Parsed JSON value or default.

    Example:
        >>> safe_json_loads('{"key": "value"}')
        {'key': 'value'}
        >>> safe_json_loads('invalid', default={})
        {}
    """
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return default

def safe_json_dumps(value: Any, ensure_ascii: bool = False, **kwargs) -> str:
    """Serialize a value to JSON string with error handling.

    Args:
        value: Value to serialize.
        ensure_ascii: If False, preserve non-ASCII characters (default: False).
        **kwargs: Additional arguments for json.dumps.

    Returns:
        str: JSON string.

    Raises:
        ValidationError: If the value cannot be serialized to JSON.

    Example:
        >>> safe_json_dumps({"key": "value"})
        '{"key": "value"}'
    """
    try:
        return json.dumps(value, ensure_ascii=ensure_ascii, **kwargs)
    except (TypeError, ValueError) as e:
        raise ValidationError(f"Cannot serialize to JSON: {str(e)}")

def extract_json_field(value: Any, path: str, default: Any = None) -> Any:
    """Extract a field from a JSON-like structure using a dot/index path.

    Args:
        value: JSON-like structure (dict or list).
        path: Path to the field (e.g., 'key1.key2[0].field').
        default: Value to return if the path is invalid (default: None).

    Returns:
        Any: Extracted value or default.

    Example:
        >>> value = {"key1": {"key2": [{"field": "value"}]}}
        >>> extract_json_field(value, "key1.key2[0].field")
        'value'
        >>> extract_json_field(value, "invalid.path", default="missing")
        'missing'
    """
    try:
        current = value
        for part in path.replace("[", ".").replace("]", "").split("."):
            if isinstance(current, dict):
                current = current[part]
            elif isinstance(current, list) and part.isdigit():
                current = current[int(part)]
            else:
                return default
        return current
    except (KeyError, IndexError, TypeError):
        return default

def stream_json_loads(data: str, prefix: str = "") -> Iterator[Any]:
    """Parse a JSON string in streaming mode, yielding objects or arrays incrementally.

    Args:
        data: JSON string to parse.
        prefix: Optional ijson prefix for specific parsing (e.g., 'items' for array items).

    Yields:
        Iterator[Any]: Parsed JSON objects or array items.

    Raises:
        ValidationError: If the JSON is invalid or ijson is not installed and needed.

    Example:
        >>> data = '[{"id": 1}, {"id": 2}]'
        >>> list(stream_json_loads(data))
        [{'id': 1}, {'id': 2}]
    """
    if ijson is None:
        try:
            # Fallback to non-streaming for small JSON
            parsed = json.loads(data)
            if isinstance(parsed, list):
                for item in parsed:
                    yield item
            elif isinstance(parsed, dict):
                yield parsed
            else:
                raise ValidationError("Streaming only supports JSON arrays or objects")
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON for streaming: {str(e)}")
    else:
        try:
            parser = ijson.parse(data)
            for prefix, event, value in parser:
                if event == "map_key" or event == "start_map" or event == "start_array":
                    continue
                if event == "end_map" or event == "end_array":
                    yield value
        except ijson.JSONError as e:
            raise ValidationError(f"Invalid JSON for streaming: {str(e)}")