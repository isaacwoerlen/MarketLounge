from __future__ import annotations
import json
from typing import Any, List, Optional
from functools import lru_cache
from decouple import Config, RepositoryEnv  # type: ignore
from utils_core.errors import ValidationError

__all__ = ["get_env_variable", "load_env_config", "is_env_valid"]

@lru_cache(maxsize=100)
def get_env_variable(key: str, cast: str = "str", default: Any = None) -> Any:
    """Retrieve an environment variable with optional type casting.

    Args:
        key: Environment variable name.
        cast: Type to cast the value to ('str', 'int', 'float', 'bool', 'json') (default: 'str').
        default: Default value if the variable is not set (default: None).

    Returns:
        Any: Casted value of the environment variable.

    Raises:
        ValidationError: If the variable is missing and no default is provided, or if casting fails.

    Example:
        >>> get_env_variable("EMBEDDING_DIM", cast="int", default=384)
        384
        >>> get_env_variable("CONFIG", cast="json")
        {'key': 'value'}
    """
    config = Config(RepositoryEnv(".env"))
    value = config(key, default=default)
    if value is None:
        raise ValidationError(f"Missing environment variable: {key}")

    if cast == "str":
        return str(value)
    elif cast == "int":
        try:
            return int(value)
        except (ValueError, TypeError):
            raise ValidationError(f"Cannot cast {key}={value!r} to int")
    elif cast == "float":
        try:
            return float(value)
        except (ValueError, TypeError):
            raise ValidationError(f"Cannot cast {key}={value!r} to float")
    elif cast == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "y")
        raise ValidationError(f"Cannot cast {key}={value!r} to bool")
    elif cast == "json":
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            raise ValidationError(f"Cannot cast {key}={value!r} to JSON")
    else:
        raise ValidationError(f"Unsupported cast type: {cast}")

def load_env_config(file_path: str) -> None:
    """Load environment configuration from a .env file.

    Args:
        file_path: Path to the .env file.

    Raises:
        ValidationError: If the file cannot be loaded.

    Example:
        >>> load_env_config(".env")
    """
    try:
        Config(RepositoryEnv(file_path))
    except Exception as e:
        raise ValidationError(f"Failed to load .env file {file_path}: {str(e)}")

def is_env_valid(required: List[str]) -> bool:
    """Check if all required environment variables are set.

    Args:
        required: List of required environment variable names.

    Returns:
        bool: True if all variables are set, False otherwise.

    Raises:
        ValidationError: If any required variable is missing.

    Example:
        >>> is_env_valid(["EMBEDDING_DIM", "LLM_TIMEOUT"])
        True
    """
    config = Config(RepositoryEnv(".env"))
    missing = [key for key in required if config(key, default=None) is None]
    if missing:
        raise ValidationError(f"Missing required environment variables: {', '.join(missing)}")
    return True