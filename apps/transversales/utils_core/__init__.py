"""
Utils_core: Transverse utility functions for MarketLounge.

This module centralizes imports for commonly used utilities, ensuring modularity
and ease of use across apps (e.g., matching, language, LLM_ai). Functions are
re-exported here for convenience, following the 'no-overlap' principle and
ensuring no business logic is included.

Usage:
    from utils_core import compute_checksum, timer, normalize_text
"""

from .utils import compute_checksum, slugify
from .decorators import retry_on_exception
from .time_utils import timer, utc_now, timestamp_ms, format_duration, parse_iso8601
from .text_cleaning import normalize_text, remove_accents, strip_html, standardize_whitespace
from .validators import validate_lang, normalize_locale, validate_tenant_id, validate_scope, validate_checksum, validate_json_field
from .metrics import log_metric, format_tags, record_metric_wrapper
from .alerts import validate_alerts, format_alert, merge_alerts
from .json_utils import safe_json_loads, safe_json_dumps, extract_json_field
from .env import get_env_variable, load_env_config, is_env_valid
from .logging_utils import setup_logging, get_logger, log_with_tags, log_exception
from .time_utils import timer
from .types import Alert, Payload, MetricTags, TenantInfo, MatchFilters, TranslationJobPayload

__all__ = [
    # utils.py
    "compute_checksum",
    "slugify",
    # decorators.py
    "retry_on_exception",
    # time_utils.py
    "timer",
    "utc_now",
    "timestamp_ms",
    "format_duration",
    "parse_iso8601",
    # text_cleaning.py
    "normalize_text",
    "remove_accents",
    "strip_html",
    "standardize_whitespace",
    # validators.py
    "validate_lang",
    "normalize_locale",
    "validate_tenant_id",
    "validate_scope",
    "validate_checksum",
    "validate_json_field",
    # metrics.py
    "log_metric",
    "format_tags",
    "record_metric_wrapper",
    # alerts.py
    "validate_alerts",
    "format_alert",
    "merge_alerts",
    # json_utils.py
    "safe_json_loads",
    "safe_json_dumps",
    "extract_json_field",
    # env.py
    "get_env_variable",
    "load_env_config",
    "is_env_valid",
    # logging_utils.py
    "setup_logging",
    "get_logger",
    "log_with_tags",
    "log_exception",
    # types.py
    "Alert",
    "Payload",
    "MetricTags",
    "TenantInfo",
    "MatchFilters",
    "TranslationJobPayload",
]