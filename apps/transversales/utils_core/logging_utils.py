# utils_core/logging_utils.py
from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping, Optional, Union
import contextvars

try:
    from django.conf import settings  # type: ignore
except Exception:  # pragma: no cover
    class _S:  # type: ignore
        pass
    settings = _S()  # type: ignore

# Normalisation des tags (source unique)
from utils_core.metrics import format_tags  # lean & cohérent

__all__ = ["setup_logging", "get_logger", "log_with_tags", "log_exception"]

# -----------------------------------------------------------------------------
# Contexte (trace id)
# -----------------------------------------------------------------------------
TRACE_ID: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("trace_id", default=None)

def _now_iso() -> str:
    # ISO 8601 en UTC avec millisecondes
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

def _level_to_int(level: Union[int, str]) -> int:
    if isinstance(level, int):
        return level
    name = str(level).upper()
    return logging.getLevelName(name) if isinstance(logging.getLevelName(name), int) else logging.INFO

def _json_default(o: Any) -> str:
    # Fallback sûr pour objets non sérialisables
    try:
        return str(o)
    except Exception:
        return "<unserializable>"

# -----------------------------------------------------------------------------
# Formatters
# -----------------------------------------------------------------------------
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload: MutableMapping[str, Any] = {
            "ts": _now_iso(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Tags normalisés (passés via extra={"tags": {...}})
        tags_obj = getattr(record, "tags", None)
        if tags_obj:
            payload["tags"] = format_tags(tags_obj, as_string=False)

        # Trace id (depuis contextvar ou extra)
        trace_id = getattr(record, "trace_id", None) or TRACE_ID.get()
        if trace_id:
            payload["trace_id"] = str(trace_id)

        # Extra arbitraire (extra={"extra": {...}})
        extra_obj = getattr(record, "extra", None)
        if isinstance(extra_obj, Mapping) and extra_obj:
            payload["extra"] = dict(extra_obj)

        # Exception structurée
        if record.exc_info:
            etype, evalue, etb = record.exc_info
            payload["exc"] = {
                "type": getattr(etype, "__name__", str(etype)),
                "message": str(evalue),
                "stack": "".join(traceback.format_exception(etype, evalue, etb)),
            }

        return json.dumps(payload, ensure_ascii=False, default=_json_default)

class TextFormatter(logging.Formatter):
    # Ligne compacte : [ts] level logger msg | tags=... trace_id=...
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        ts = _now_iso()
        base = f"[{ts}] {record.levelname.lower()} {record.name} - {record.getMessage()}"
        parts = [base]
        tags_obj = getattr(record, "tags", None)
        if tags_obj:
            parts.append(f"tags={format_tags(tags_obj, as_string=True)}")
        trace_id = getattr(record, "trace_id", None) or TRACE_ID.get()
        if trace_id:
            parts.append(f"trace_id={trace_id}")
        if record.exc_info:
            parts.append("exc=" + self.formatException(record.exc_info))  # type: ignore[arg-type]
        return " | ".join(parts)

# -----------------------------------------------------------------------------
# Setup / Factory
# -----------------------------------------------------------------------------
def setup_logging(
    *,
    level: Union[int, str, None] = None,
    json_output: Optional[bool] = None,
    logger_name: Optional[str] = None,
    reset: bool = False,
) -> logging.Logger:
    """
    Configure un logger stdout minimal, idempotent.
    - level : "INFO", "DEBUG", etc. (fallback: settings.LOG_LEVEL ou INFO)
    - json_output : True/False (fallback: settings.LOG_JSON ou True)
    - logger_name : nom principal (fallback: settings.APP_LOGGER_NAME ou 'themarketlounge')
    - reset : si True, supprime les handlers existants du logger cible
    """
    name = logger_name or getattr(settings, "APP_LOGGER_NAME", "themarketlounge")
    logger = logging.getLogger(name)

    lvl = level or getattr(settings, "LOG_LEVEL", "INFO")
    logger.setLevel(_level_to_int(lvl))

    want_json = json_output
    if want_json is None:
        want_json = bool(getattr(settings, "LOG_JSON", True))

    if reset:
        logger.handlers[:] = []

    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(JsonFormatter() if want_json else TextFormatter())
        logger.addHandler(handler)
        logger.propagate = False  # éviter double logging via root

    return logger

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Récupère un logger par nom, ou le logger principal configuré.
    """
    base = getattr(settings, "APP_LOGGER_NAME", "themarketlounge")
    return logging.getLogger(name or base)

# -----------------------------------------------------------------------------
# Structured logging helpers
# -----------------------------------------------------------------------------
def log_with_tags(
    logger: logging.Logger,
    level: Union[int, str],
    msg: str,
    *,
    tags: Optional[Mapping[str, object]] = None,
    extra: Optional[Mapping[str, object]] = None,
    trace_id: Optional[str] = None,
    exc_info: Any = None,
) -> None:
    """
    Log structuré avec tags normalisés et extra arbitraire.
    """
    # NOTE: normalisation des tags faite dans le Formatter pour conserver l'ordonnancement
    logger.log(
        _level_to_int(level),
        msg,
        extra={"tags": tags or {}, "extra": extra or {}, "trace_id": trace_id},
        exc_info=exc_info,
    )

def log_exception(
    logger: logging.Logger,
    exc: BaseException,
    msg: str = "Unhandled exception",
    *,
    tags: Optional[Mapping[str, object]] = None,
    extra: Optional[Mapping[str, object]] = None,
    level: Union[int, str] = "ERROR",
) -> None:
    """
    Log une exception avec pile, tags et extra.
    """
    logger.log(
        _level_to_int(level),
        msg,
        extra={"tags": tags or {}, "extra": extra or {}},
        exc_info=(type(exc), exc, exc.__traceback__),
    )
