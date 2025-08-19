# utils_core/env.py
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Dict, Mapping, MutableMapping, Optional, Tuple, Union

try:  # Optionnel: meilleure DX sous Django (prefix configurable via settings)
    from django.conf import settings  # type: ignore
except Exception:  # pragma: no cover
    class _S:  # type: ignore
        pass
    settings = _S()  # type: ignore

__all__ = ["get_env_variable", "load_env_config", "is_env_valid"]

# ──────────────────────────────────────────────────────────────────────────────
# Configuration Schema
# ──────────────────────────────────────────────────────────────────────────────

ENV_SCHEMA: Dict[str, Dict[str, Any]] = {
    "EMBEDDING_DIM": {
        "cast": "int",
        "default": 384,
        "required": False,
        "min_value": 128,
        "max_value": 2048,
        "description": "Dimension des embeddings pour matching (ex. : sentence-transformers)."
    },
    "LLM_TIMEOUT": {
        "cast": "float",
        "default": 5.0,
        "required": False,
        "min_value": 1.0,
        "max_value": 30.0,
        "description": "Timeout en secondes pour appels LLM (language, LLM_ai)."
    },
    "LANG_BATCH_SIZE": {
        "cast": "int",
        "default": 200,
        "required": False,
        "min_value": 1,
        "max_value": 1000,
        "description": "Taille des batches pour traduction (language)."
    },
    "MATCH_TOPK_DEFAULT": {
        "cast": "int",
        "default": 100,
        "required": False,
        "min_value": 1,
        "max_value": 1000,
        "description": "Nombre par défaut de résultats pour matching."
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_TRUE = {"1", "true", "yes", "on", "y", "t"}
_FALSE = {"0", "false", "no", "off", "n", "f"}
_SECRET_HINTS = ("SECRET", "TOKEN", "KEY", "PASSWORD")

def _mask(name: str, value: Any) -> Any:
    """Masque les secrets détectés par heuristique simple."""
    if value is None:
        return value
    upper = name.upper()
    if any(h in upper for h in _SECRET_HINTS):
        s = str(value)
        if len(s) <= 8:
            return "********"
        return s[:4] + "…****"
    return value

def _coerce(value: Optional[str], caster: Union[str, Callable[[str], Any]]) -> Any:
    """Convertit la chaîne selon 'caster' (str|int|float|bool|json|list|callable)."""
    if value is None:
        return None
    if callable(caster):
        return caster(value)

    t = (caster or "str").lower()
    v = value.strip()

    if t == "str":
        return v
    if t == "int":
        return int(v)
    if t == "float":
        return float(v)
    if t == "bool":
        lv = v.lower()
        if lv in _TRUE:
            return True
        if lv in _FALSE:
            return False
        raise ValueError(f"Cannot coerce '{value}' to bool")
    if t == "json":
        return json.loads(v or "null")
    if t in ("list", "csv"):
        # Ex: "a, b ,c" -> ["a","b","c"] (vide -> [])
        return [x.strip() for x in v.split(",")] if v else []
    raise ValueError(f"Unknown cast type: {caster}")

# ──────────────────────────────────────────────────────────────────────────────
# API
# ──────────────────────────────────────────────────────────────────────────────

def get_env_variable(
    name: str,
    *,
    prefix: Optional[str] = None,
    default: Any = None,
    cast: Union[str, Callable[[str], Any]] = "str",
    required: bool = False,
    strip: bool = True,
    pattern: Optional[str] = None,
    choices: Optional[Iterable[Any]] = None,
    min_value: Optional[Union[int, float]] = None,
    max_value: Optional[Union[int, float]] = None,
    non_empty: bool = False,
    debug_log: bool = False,
) -> Any:
    """
    Récupère une variable d'environnement avec validation et conversion.
    - Utilisé pour centraliser les settings partagés (ex. : EMBEDDING_DIM, LLM_TIMEOUT).
    - Supporte multi-tenancy via prefix (ex. : 'tenant_123_EMBEDDING_DIM').
    - Utilisé dans language (LANG_BATCH_SIZE), matching (EMBEDDING_DIM, MATCH_TOPK_DEFAULT),
      et LLM_ai (LLM_TIMEOUT).

    Args:
        name: Nom de la variable (ex. : 'EMBEDDING_DIM').
        prefix: Préfixe optionnel pour multi-tenancy (ex. : 'tenant_123_').
        default: Valeur par défaut si absente.
        cast: Type de conversion ('str', 'int', 'float', 'bool', 'json', 'list', ou callable).
        required: Si True, lève une erreur si absente.
        strip: Supprime les espaces si True.
        pattern: Regex pour validation.
        choices: Liste de valeurs autorisées.
        min_value: Valeur minimale (pour int/float).
        max_value: Valeur maximale (pour int/float).
        non_empty: Si True, interdit les chaînes vides.
        debug_log: Log les accès si True.

    Returns:
        Valeur convertie ou default.

    Raises:
        ValueError: Si validation échoue (ex. : pattern non respecté, hors limites).

    Examples:
        >>> from utils_core.env import get_env_variable
        >>> get_env_variable("EMBEDDING_DIM", cast="int", default=384)  # matching: dimension embeddings
        384
        >>> get_env_variable("LLM_TIMEOUT", prefix="tenant_123_", cast="float", default=5.0)  # language: LLM timeout
        5.0
        >>> get_env_variable("MATCH_TOPK_DEFAULT", cast="int", default=100)  # matching: top_k
        100
    """
    key = f"{prefix}{name}" if prefix else name
    value = os.getenv(key)

    if value is None:
        if required:
            raise ValueError(f"Missing required environment variable: {key}")
        return default

    if strip:
        value = value.strip()

    if non_empty and value == "":
        raise ValueError(f"Environment variable {key} cannot be empty")

    try:
        value = _coerce(value, cast)
    except Exception as e:
        raise ValueError(f"Cannot coerce {key} to {cast}: {e}")

    if pattern and not re.match(pattern, str(value)):
        raise ValueError(f"Environment variable {key} does not match pattern {pattern}")

    if choices and value not in choices:
        raise ValueError(f"Environment variable {key} must be one of {choices}")

    if isinstance(value, (int, float)):
        if min_value is not None and value < min_value:
            raise ValueError(f"Environment variable {key} below minimum {min_value}")
        if max_value is not None and value > max_value:
            raise ValueError(f"Environment variable {key} above maximum {max_value}")

    if debug_log:
        print(f"Env {key}: {_mask(name, value)}")

    return value

def load_env_config(
    schema: Mapping[str, Mapping[str, Any]],
    *,
    prefix: Optional[str] = None,
    stop_on_error: bool = False,
) -> MutableMapping[str, Any]:
    """
    Charge plusieurs variables d'environnement selon un schéma.
    """
    cfg: MutableMapping[str, Any] = {}
    errors: Dict[str, str] = {}

    for key, opts in schema.items():
        try:
            cfg[key] = get_env_variable(
                key,
                prefix=prefix,
                default=opts.get("default"),
                cast=opts.get("cast", "str"),
                required=opts.get("required", False),
                strip=opts.get("strip", True),
                pattern=opts.get("pattern"),
                choices=opts.get("choices"),
                min_value=opts.get("min_value"),
                max_value=opts.get("max_value"),
                non_empty=opts.get("non_empty", False),
                debug_log=opts.get("debug_log", False),
            )
        except Exception as e:
            if stop_on_error:
                raise
            errors[key] = str(e)

    if errors:
        # On expose les erreurs mais on retourne quand même la partie valide
        cfg["_errors"] = errors
    return cfg

def is_env_valid(
    config_or_schema: Mapping[str, Any],
    *,
    prefix: Optional[str] = None,
    as_schema: bool = False,
) -> Tuple[bool, Dict[str, str]]:
    """
    Valide soit:
      - un 'config' déjà chargé (as_schema=False, défaut),
      - un 'schema' d'entrée (as_schema=True) en tentant de charger.
    """
    if not as_schema:
        # Valide une config déjà construite (vérifications minimales)
        errors: Dict[str, str] = {}
        for k, v in config_or_schema.items():
            # Exemple minimal: non vide si explicitement requis via convention *_REQUIRED
            if k.endswith("_REQUIRED") and not v:
                errors[k] = "Required flag set but value is empty"
        return (len(errors) == 0, errors)

    # Valide un schéma en tentant un chargement permissif
    schema: Mapping[str, Mapping[str, Any]] = config_or_schema  # type: ignore
    errors: Dict[str, str] = {}
    for key, opts in schema.items():
        try:
            _ = get_env_variable(
                key,
                prefix=prefix,
                default=opts.get("default"),
                cast=opts.get("cast", "str"),
                required=opts.get("required", False),
                strip=opts.get("strip", True),
                pattern=opts.get("pattern"),
                choices=opts.get("choices"),
                min_value=opts.get("min_value"),
                max_value=opts.get("max_value"),
                non_empty=opts.get("non_empty", False),
                debug_log=False,
            )
        except Exception as e:
            errors[key] = str(e)
    return (len(errors) == 0, errors)
    