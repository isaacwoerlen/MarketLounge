# utils_core/metrics.py
from __future__ import annotations

import json
import logging
import re
import time
from typing import Callable, Mapping, MutableMapping, Optional

try:
    from django.conf import settings
    from django.utils.module_loading import import_string
except Exception:  # pragma: no cover
    class _S:  # type: ignore
        pass
    settings = _S()  # type: ignore

# ⇩ Noms de métriques standard (référence unique dans constants.py)
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

__all__ = [
    # API publique
    "format_tags", "log_metric", "record_metric_wrapper",
    # Noms de métriques standard ré-exportés
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

# ──────────────────────────────────────────────────────────────────────────────
# Logger & options
# ──────────────────────────────────────────────────────────────────────────────

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

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _now_ms() -> int:
    return int(time.time() * 1000)

def format_tags(tags: Mapping[str, object], *, as_string: bool = True) -> Union[str, Mapping[str, str]]:
    """
    Normalise les tags pour métriques.
    - Clef: [a-z0-9_], lower, max 64 chars
    - Valeur: str, max 256 chars
    - as_string=True → retourne "k1:v1,k2:v2"
    - as_string=False → retourne dict

    Examples:
        >>> format_tags({"tenant_id": "tenant_123", "scope": "company"})
        'tenant_id:tenant_123,scope:company'
        >>> format_tags({"env": "prod"}, as_string=False)
        {'env': 'prod'}
    """
    if not tags:
        return "" if as_string else {}
    
    clean: MutableMapping[str, str] = {}
    for k, v in tags.items():
        k = re.sub(r"[^a-z0-9_]", "_", str(k).lower()).strip("_")[:64]
        if not k:
            continue
        v = str(v).replace(",", "_").replace("\n", "_")[:256]
        clean[k] = v
    
    if as_string:
        return ",".join(f"{k}:{v}" for k, v in sorted(clean.items()))
    return clean

def _emit_metric(
    name: str,
    value: float,
    tags: Mapping[str, str],
    ts_ms: Optional[int],
) -> None:
    """
    Émet une métrique via logger et sink (si configuré).
    """
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
        "ts_ms": ts_ms or _now_ms(),
    }
    _logger.info(json.dumps(payload, ensure_ascii=False))

def log_metric(
    name: str,
    value: float,
    *,
    tags: Optional[Mapping[str, object]] = None,
    ts_ms: Optional[int] = None,
) -> None:
    """
    Enregistre une métrique avec nom, valeur et tags.
    - Utilisé dans matching (ex. : METRIC_MATCH_INDEX_LATENCY, METRIC_MATCH_RECALL_K),
      language (ex. : METRIC_LANG_BULK_TRANSLATE_LAT), et curation (ex. : validation metrics).

    Args:
        name: Nom de la métrique (ex. : 'match.index_latency_ms').
        value: Valeur numérique.
        tags: Tags pour catégorisation (ex. : {'tenant_id': 'tenant_123'}).
        ts_ms: Timestamp en millisecondes (optionnel).

    Examples:
        >>> from utils_core.metrics import log_metric, METRIC_MATCH_RECALL_K
        >>> log_metric(METRIC_MATCH_RECALL_K, 0.9, tags={'tenant_id': 'tenant_123', 'scope': 'company'})
    """
    if not isinstance(value, (int, float)):
        raise TypeError("value must be numeric")
    ntags = format_tags(tags or {}, as_string=False)  # type: ignore[arg-type]
    _emit_metric(name, float(value), ntags, ts_ms)

def record_metric_wrapper(
    base_name: str,
    *,
    static_tags: Optional[Mapping[str, object]] = None,
    dynamic_tags: Optional[Callable[[], Mapping[str, object]]] = None,
    latency_metric: Optional[str] = None,
    success_metric: Optional[str] = None,
    error_metric: Optional[str] = None,
) -> Callable:
    """
    Décorateur pour instrumenter automatiquement une fonction avec des métriques.
    - Enregistre latency_ms, success, et error avec tags statiques et dynamiques.
    - Utilisé dans matching (ex. : hybrid_search latency), language (ex. : batch translation),
      et LLM_ai (ex. : enrich_text).

    Args:
        base_name: Nom de base pour les métriques (ex. : 'match.hybrid_search').
        static_tags: Tags fixes (ex. : {'env': 'prod'}).
        dynamic_tags: Fonction retournant des tags dynamiques (ex. : lambda: {'tenant_id': get_current_tenant()}).
        latency_metric: Nom de la métrique de latence (défaut : '{base_name}.latency_ms').
        success_metric: Nom de la métrique de succès (défaut : '{base_name}.success').
        error_metric: Nom de la métrique d'erreur (défaut : '{base_name}.error').

    Returns:
        Callable: Fonction décorée avec métriques.

    Examples:
        >>> from utils_core.metrics import record_metric_wrapper
        >>> @record_metric_wrapper('match.hybrid_search', static_tags={'scope': 'company'},
        ...                        dynamic_tags=lambda: {'tenant_id': get_current_tenant()})
        ... def hybrid_search(query, tenant_id, scope): ...  # matching: monitor latency
        >>> @record_metric_wrapper('lang.batch_translate', static_tags={'operation': 'batch'})
        ... def batch_translate_scope(scope, source_lang, target_langs): ...  # language: monitor translation
    """
    lat_name = latency_metric or f"{base_name}.latency_ms"
    ok_name = success_metric or f"{base_name}.success"
    err_name = error_metric or f"{base_name}.error"
    base_tags = format_tags(static_tags or {}, as_string=False)  # type: ignore[arg-type]

    def _decorator(fn):
        def _wrap(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                final_tags = base_tags.copy()
                if dynamic_tags:
                    final_tags.update(format_tags(dynamic_tags(), as_string=False))
                log_metric(lat_name, elapsed_ms, tags=final_tags)
                log_metric(ok_name, 1, tags=final_tags)
                return result
            except Exception:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                final_tags = base_tags.copy()
                if dynamic_tags:
                    final_tags.update(format_tags(dynamic_tags(), as_string=False))
                log_metric(lat_name, elapsed_ms, tags=final_tags)
                log_metric(err_name, 1, tags=final_tags)
                raise
        _wrap.__name__ = getattr(fn, "__name__", "wrapped")
        _wrap.__doc__ = getattr(fn, "__doc__", None)
        _wrap.__qualname__ = getattr(fn, "__qualname__", _wrap.__name__)
        return _wrap
    return _decorator