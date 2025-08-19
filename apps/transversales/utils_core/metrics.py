from __future__ import annotations
import json
import logging
import re
from typing import Callable, Dict, Optional, Mapping, MutableMapping, Union
from functools import wraps
from utils_core.time_utils import timer
from utils_core.errors import ValidationError
from utils_core.constants import (
    METRIC_MATCH_QUERY_LATENCY,
    METRIC_MATCH_VECTOR_HITS,
    METRIC_MATCH_DIRTY_RATIO,
    METRIC_MATCH_INDEX_LATENCY,
    METRIC_MATCH_RECALL_K,
    METRIC_MATCH_FAISS_HIT,
    METRIC_MATCH_FUSION_SHARE,
    METRIC_LANG_BULK_TRANSLATE_LAT,
    METRIC_LANG_CACHE_HIT,
    METRIC_LANG_CACHE_MISS,
)

try:
    from django.conf import settings
    from django.utils.module_loading import import_string
except Exception:  # pragma: no cover
    class _S:  # type: ignore
        pass
    settings = _S()  # type: ignore

__all__ = [
    # API publique
    "format_tags",
    "log_metric",
    "record_metric_wrapper",
    # Constantes réexportées
    "METRIC_MATCH_QUERY_LATENCY",
    "METRIC_MATCH_VECTOR_HITS",
    "METRIC_MATCH_DIRTY_RATIO",
    "METRIC_MATCH_INDEX_LATENCY",
    "METRIC_MATCH_RECALL_K",
    "METRIC_MATCH_FAISS_HIT",
    "METRIC_MATCH_FUSION_SHARE",
    "METRIC_LANG_BULK_TRANSLATE_LAT",
    "METRIC_LANG_CACHE_HIT",
    "METRIC_LANG_CACHE_MISS",
]

# Logger & options
_LOGGER_NAME = getattr(settings, "METRICS_LOGGER_NAME", "metrics")
_logger = logging.getLogger(_LOGGER_NAME)

_sink: Optional[Callable[[str, float, Mapping[str, str], Optional[int]], None]] = None
_sink_setting = getattr(settings, "METRICS_SINK", None)
if callable(_sink_setting):
    _sink = _sink_setting
elif isinstance(_sink_setting, str):
    try:
        _sink = import_string(_sink_setting)  # type: ignore
    except Exception:  # pragma: no cover
        _sink = None

_statsd_client = None
if getattr(settings, "METRICS_BACKEND", "").lower() == "statsd":  # pragma: no cover
    try:
        import statsd  # type: ignore
        host = getattr(settings, "STATSD_HOST", "127.0.0.1")
        port = int(getattr(settings, "STATSD_PORT", 8125))
        prefix = getattr(settings, "STATSD_PREFIX", "")
        _statsd_client = statsd.StatsClient(host=host, port=port, prefix=prefix)
    except Exception:  # pragma: no cover
        _statsd_client = None

def format_tags(tags: Mapping[str, object], tenant_id: Optional[str] = None, *, as_string: bool = True) -> Union[str, Mapping[str, str]]:
    """Format metric tags into a string or dict, including tenant_id if provided.

    Args:
        tags: Dictionary of tag key-value pairs.
        tenant_id: Optional tenant identifier (e.g., 'tenant_123').
        as_string: If True, return string (e.g., 'key1=value1,tenant_id=tenant_123'); else dict.

    Returns:
        Union[str, Mapping[str, str]]: Formatted tags as string or dict.

    Raises:
        ValidationError: If tenant_id is invalid (must start with 'tenant_').

    Example:
        >>> format_tags({"operation": "search"}, tenant_id="tenant_123")
        'operation=search,tenant_id=tenant_123'
        >>> format_tags({"env": "prod"}, as_string=False)
        {'env': 'prod'}
    """
    clean: MutableMapping[str, str] = {}
    if tenant_id:
        if not tenant_id.startswith("tenant_"):
            raise ValidationError(f"Invalid tenant_id: {tenant_id}")
        clean["tenant_id"] = tenant_id
    for k, v in tags.items():
        k = re.sub(r"[^a-z0-9_]", "_", str(k).lower()).strip("_")[:64]
        if not k:
            continue
        v = str(v).replace(",", "_").replace("\n", "_")[:256]
        clean[k] = v
    if as_string:
        return ",".join(f"{k}={v}" for k, v in sorted(clean.items()))
    return clean

def _emit_metric(name: str, value: float, tags: Mapping[str, str], ts_ms: Optional[int]) -> None:
    """Emit a metric via logger, StatsD, or custom sink."""
    if _statsd_client:  # pragma: no cover
        tag_str = format_tags(tags, as_string=True)
        name = re.sub(r"[^a-z0-9_\.]", "_", name.lower())
        _statsd_client.gauge(f"{name}", value, tags=tag_str.split(",") if tag_str else None)
    if _sink:
        _sink(name, value, tags, ts_ms)
    payload = {
        "name": name,
        "value": float(value),
        "tags": dict(tags) if tags else {},
        "ts_ms": ts_ms or int(time.time() * 1000),
    }
    _logger.info(json.dumps(payload, ensure_ascii=False))

def log_metric(
    name: str,
    value: float,
    tags: Optional[Mapping[str, object]] = None,
    tenant_id: Optional[str] = None,
    ts_ms: Optional[int] = None,
) -> None:
    """Log a metric value to Prometheus, StatsD, or logger with optional tags and tenant_id.

    Args:
        name: Metric name (e.g., 'match.query.latency_ms').
        value: Numeric value.
        tags: Optional dictionary of tags (e.g., {'scope': 'company'}).
        tenant_id: Optional tenant identifier (e.g., 'tenant_123').
        ts_ms: Optional timestamp in milliseconds.

    Raises:
        TypeError: If value is not numeric.

    Example:
        >>> log_metric("match.query.latency_ms", 150.5, {"scope": "company"}, tenant_id="tenant_123")
    """
    if not isinstance(value, (int, float)):
        raise TypeError("value must be numeric")
    ntags = format_tags(tags or {}, tenant_id=tenant_id, as_string=False)
    _emit_metric(name, float(value), ntags, ts_ms)

def record_metric_wrapper(
    base_name: str,
    static_tags: Optional[Mapping[str, object]] = None,
    dynamic_tags: Optional[Callable[[], Mapping[str, object]]] = None,
    latency_metric: Optional[str] = None,
    success_metric: Optional[str] = None,
    error_metric: Optional[str] = None,
) -> Callable:
    """Decorator to record execution time and success/failure of a function.

    Args:
        base_name: Base name for metrics (e.g., 'match.hybrid_search').
        static_tags: Static tags (e.g., {'env': 'prod'}).
        dynamic_tags: Function returning dynamic tags (e.g., lambda: {'tenant_id': get_current_tenant()}).
        latency_metric: Name for latency metric (default: '{base_name}.latency_ms').
        success_metric: Name for success metric (default: '{base_name}.success').
        error_metric: Name for error metric (default: '{base_name}.error').

    Returns:
        Callable: Decorated function with metric recording.

    Example:
        >>> @record_metric_wrapper('match.hybrid_search', static_tags={'scope': 'company'})
        ... def hybrid_search(query, tenant_id, scope): ...
    """
    lat_name = latency_metric or f"{base_name}.latency_ms"
    ok_name = success_metric or f"{base_name}.success"
    err_name = error_metric or f"{base_name}.error"
    base_tags = format_tags(static_tags or {}, as_string=False)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, tenant_id: Optional[str] = None, **kwargs) -> Any:
            with timer() as t:
                try:
                    result = func(*args, **kwargs)
                    final_tags = base_tags.copy()
                    if dynamic_tags:
                        final_tags.update(format_tags(dynamic_tags(), tenant_id=tenant_id, as_string=False))
                    else:
                        final_tags = format_tags(final_tags, tenant_id=tenant_id, as_string=False)
                    log_metric(lat_name, t.elapsed_ms, tags=final_tags)
                    log_metric(ok_name, 1, tags=final_tags)
                    return result
                except Exception:
                    final_tags = base_tags.copy()
                    if dynamic_tags:
                        final_tags.update(format_tags(dynamic_tags(), tenant_id=tenant_id, as_string=False))
                    else:
                        final_tags = format_tags(final_tags, tenant_id=tenant_id, as_string=False)
                    log_metric(lat_name, t.elapsed_ms, tags=final_tags)
                    log_metric(err_name, 1, tags=final_tags)
                    raise
        return wrapper
    return decorator