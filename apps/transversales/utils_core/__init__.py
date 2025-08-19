# utils_core/__init__.py
from .metrics import log_metric
from .json_utils import safe_json_loads, safe_json_dumps
from .time_utils import utc_now, timestamp_ms
from .utils import compute_checksum, retry_on_exception, slugify, Timer
from .validators import normalize_locale, validate_lang
from .text_cleaning import normalize_text
from .alerts import validate_alerts, merge_alerts
from .errors import AlertException
from .env import get_env_variable

__all__ = [
    "log_metric",
    "safe_json_loads",
    "safe_json_dumps",
    "utc_now",
    "timestamp_ms",
    "compute_checksum",
    "retry_on_exception",
    "slugify",
    "Timer",
    "normalize_locale",
    "validate_lang",
    "normalize_text",
    "validate_alerts",
    "merge_alerts",
    "AlertException",
    "get_env_variable",
]