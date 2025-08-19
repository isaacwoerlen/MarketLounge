# utils_core/json_utils.py
from __future__ import annotations

import json
import re
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple, Union

try:  # Optionnel : ValidationError si Django est dispo
    from django.core.exceptions import ValidationError
except Exception:  # pragma: no cover
    class ValidationError(Exception):  # type: ignore
        pass

from utils_core.constants import (
    DEFAULT_JSON_MAX_BYTES,
    ERR_JSON_TOO_LARGE,
    ERR_JSON_INVALID_TYPE,
)

__all__ = ["safe_json_loads", "safe_json_dumps", "extract_json_field"]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _byte_len(s: Union[str, bytes, bytearray]) -> int:
    if isinstance(s, (bytes, bytearray)):
        return len(s)
    return len(s.encode("utf-8"))

def _ensure_text(data: Union[str, bytes, bytearray]) -> str:
    if isinstance(data, (bytes, bytearray)):
        text = bytes(data).decode("utf-8", errors="strict")
    else:
        text = str(data)
    # Retire éventuel BOM et espaces parasites
    if text and text[0] == "\ufeff":
        text = text[1:]
    return text.strip()

# Parseur de chemin "a.b[2].c" → ["a", 2, "c"]
_PATH_TOKENIZER = re.compile(r"""
    (?:^|\.)([^\.\[\]]+)      # segment alpha-num/underscore entre points
    | \[(\d+)\]               # index de liste entre crochets
""", re.VERBOSE)

def _parse_path(path: Union[str, Sequence[Union[str, int]]]) -> List[Union[str, int]]:
    if isinstance(path, (list, tuple)):
        return [int(p) if isinstance(p, str) and p.isdigit() else p for p in path]
    out: List[Union[str, int]] = []
    for m in _PATH_TOKENIZER.finditer(str(path)):
        key, idx = m.groups()
        if key is not None:
            out.append(key)
        else:
            out.append(int(idx))  # type: ignore[arg-type]
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def safe_json_loads(
    data: Optional[Union[str, bytes, bytearray]],
    *,
    default: Any = None,
    max_bytes: Optional[int] = DEFAULT_JSON_MAX_BYTES,
    strict: bool = True,
    parse_float=None,
    parse_int=None,
    parse_constant=None,
    on_error: str = "return_default",  # "return_default" | "raise"
) -> Any:
    """
    Charge du JSON de manière sûre.
    - Supporte str/bytes/bytearray (UTF-8 strict), retire BOM.
    - Enforce max_bytes (UTF-8).
    - Renvoie 'default' sur erreur si on_error='return_default' (défaut).

    Raises:
        ValidationError si on_error='raise' et problème taille/parse.
    """
    if data is None or data == "":
        return default

    # Taille
    if max_bytes is not None and _byte_len(data) > int(max_bytes):
        if on_error == "raise":
            raise ValidationError(ERR_JSON_TOO_LARGE)
        return default

    try:
        text = _ensure_text(data)
        return json.loads(
            text,
            strict=strict,
            parse_float=parse_float,
            parse_int=parse_int,
            parse_constant=parse_constant,
        )
    except Exception as e:
        if on_error == "raise":
            raise ValidationError(str(e))
        return default


def safe_json_dumps(
    obj: Any,
    *,
    ensure_ascii: bool = False,
    separators: Tuple[str, str] = (",", ":"),
    sort_keys: bool = False,
    max_bytes: Optional[int] = DEFAULT_JSON_MAX_BYTES,
    on_overflow: str = "raise",          # "raise" | "return_default"
    default_return: str = "null",
) -> str:
    """
    Sérialise en JSON de manière déterministe (compacte) et sûre.
    - ensure_ascii=False par défaut (UTF-8), séparateurs compacts.
    - Vérifie la taille (UTF-8). Si dépasse et on_overflow='return_default',
      retourne 'default_return' (ex.: "null").

    Raises:
        ValidationError si dépassement taille (on_overflow='raise') ou erreur de sérialisation.
    """
    try:
        s = json.dumps(obj, ensure_ascii=ensure_ascii, separators=separators, sort_keys=sort_keys)
    except Exception as e:
        raise ValidationError(f"{ERR_JSON_INVALID_TYPE}: {e}")

    if max_bytes is not None and _byte_len(s) > int(max_bytes):
        if on_overflow == "return_default":
            return default_return
        raise ValidationError(ERR_JSON_TOO_LARGE)
    return s


def extract_json_field(
    data: Any,
    path: Union[str, Sequence[Union[str, int]]],
    *,
    default: Any = None,
    auto_parse_string: bool = True,
) -> Any:
    """
    Extrait une valeur d'un objet JSON-like via un chemin.
    - path: "a.b[2].c" ou liste de segments ["a", 2, "c"].
    - auto_parse_string: si data est une str, tentative de JSON.loads safe.

    Exemples:
        extract_json_field({"a": {"b": [10, 20, {"c": 42}]}}, "a.b[2].c") -> 42
        extract_json_field('{"a":{"b":[1,2]}}', "a.b[1]") -> 2
    """
    # Auto parse si nécessaire
    if auto_parse_string and isinstance(data, str):
        parsed = safe_json_loads(data, default=None, on_error="return_default")
        if parsed is not None:
            data = parsed

    segments = _parse_path(path)

    cur: Any = data
    for seg in segments:
        if isinstance(seg, int):
            if isinstance(cur, Sequence) and not isinstance(cur, (str, bytes, bytearray)):
                if 0 <= seg < len(cur):
                    cur = cur[seg]
                else:
                    return default
            else:
                return default
        else:
            if isinstance(cur, Mapping):
                if seg in cur:
                    cur = cur[seg]
                else:
                    return default
            else:
                return default
    return cur
