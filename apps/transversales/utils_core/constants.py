# utils_core/constants.py
from __future__ import annotations

try:  # Optionnel: meilleure DX sous Django
    from django.conf import settings  # type: ignore
except Exception:  # pragma: no cover
    class _S:  # type: ignore
        pass
    settings = _S()  # type: ignore

# ──────────────────────────────────────────────────────────────────────────────
# Tailles & temps (unités)
KB = 1024
MB = 1024 * KB
SEC = 1
MIN = 60 * SEC
HOUR = 60 * MIN
DAY = 24 * HOUR

# ──────────────────────────────────────────────────────────────────────────────
# Defaults (overridables via settings.py)
# Embeddings (aligné avec matching)
DEFAULT_EMBEDDING_MODEL = getattr(
    settings, "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual"
)
DEFAULT_EMBEDDING_DIM = int(getattr(settings, "EMBEDDING_DIM", 384))

# JSON size limits (exploité par validate_json_field)
DEFAULT_JSON_MAX_BYTES = int(getattr(settings, "JSON_MAX_BYTES", 10 * KB))

# Cache TTLs (exploités par language + utils_core)
LANG_ACTIVE_TTL = int(getattr(settings, "LANG_ACTIVE_TTL", 6 * HOUR))
LANG_DEFAULT_TTL = int(getattr(settings, "LANG_DEFAULT_TTL", 6 * HOUR))

# Retry/backoff (pour décorateurs utilitaires)
RETRY_MAX_ATTEMPTS = int(getattr(settings, "RETRY_MAX_ATTEMPTS", 3))
RETRY_BASE_DELAY_SEC = float(getattr(settings, "RETRY_BASE_DELAY_SEC", 0.3))

# ──────────────────────────────────────────────────────────────────────────────
# Regex patterns (chaînes exportées) — utilisées par validators
TENANT_PATTERN = r"^tenant_[a-zA-Z0-9_]+$"
LANG_BCP47_PATTERN = r"^[a-z]{2}(-[a-z]{2})?$"
SHA256_HEX_PATTERN = r"^[0-9a-f]{64}$"
SCOPE_PATTERN = r"^[a-z][a-z0-9_]*(?::[a-z][a-z0-9_]*)*$"

# ──────────────────────────────────────────────────────────────────────────────
# Codes d’erreur communs (logging, ValidationError.code, métriques)
ERR_INVALID_TENANT = "invalid_tenant_id"
ERR_INVALID_LANG = "invalid_lang"
ERR_INVALID_CHECKSUM = "invalid_checksum"
ERR_INVALID_SCOPE = "invalid_scope"
ERR_JSON_TOO_LARGE = "json_too_large"
ERR_JSON_INVALID_TYPE = "invalid_json_type"

# ──────────────────────────────────────────────────────────────────────────────
# Clés de cache (formats) — centralisées pour éviter les collisions
# NB: toujours préfixer par un namespace court & stable
CACHE_NS_LANG = "lang"          # language app / features
CACHE_NS_MATCH = "match"        # matching

# Language
CK_ACTIVE_LANGS = f"{CACHE_NS_LANG}:active:{{tenant}}"      # -> list[str]
CK_DEFAULT_LANG = f"{CACHE_NS_LANG}:default:{{tenant}}"     # -> str

# Matching / embeddings — si besoin de caches auxiliaires
CK_EMBED_DIM = f"{CACHE_NS_MATCH}:dim"                       # -> int
CK_MODEL_NAME = f"{CACHE_NS_MATCH}:model"                    # -> str

# ──────────────────────────────────────────────────────────────────────────────
# Noms de métriques standardisées (pour log_metric/record_metric)
METRIC_MATCH_QUERY_LATENCY = "match.query.latency_ms"
METRIC_MATCH_VECTOR_HITS = "match.vector.hits"
METRIC_MATCH_DIRTY_RATIO = "match.index.dirty_ratio"
METRIC_MATCH_INDEX_LATENCY = "match.index_latency_ms"
METRIC_MATCH_RECALL_K = "match.recall_k"
METRIC_MATCH_FAISS_HIT = "match.faiss_hit_rate"
METRIC_MATCH_FUSION_SHARE = "match.fusion_component_share"
METRIC_LANG_BULK_TRANSLATE_LAT = "lang.bulk.latency_ms"
METRIC_LANG_CACHE_HIT = "lang.cache.hit"
METRIC_LANG_CACHE_MISS = "lang.cache.miss"

# ──────────────────────────────────────────────────────────────────────────────
# Feature flags (débrayables par settings)
FF_HYBRID_SEARCH_ENABLED = bool(getattr(settings, "FF_HYBRID_SEARCH_ENABLED", True))
FF_LANG_BULK_TRANSLATION = bool(getattr(settings, "FF_LANG_BULK_TRANSLATION", True))

# ──────────────────────────────────────────────────────────────────────────────
# Helpers de formatage de clés
def cache_key(fmt: str, **kwargs) -> str:
    """
    Sûr et centralisé : construit une clé de cache à partir d’un format.
    Ex.: cache_key(CK_ACTIVE_LANGS, tenant='tenant_acme')
    """
    return fmt.format(**kwargs)