# utils_core/types.py
from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Sequence, Iterable, Optional, Union

# Compatibilité Python 3.11+/3.10
try:  # Python 3.11+
    from typing import TypedDict, NotRequired, Required, Literal
except ImportError:  # Python 3.10
    from typing_extensions import TypedDict, NotRequired, Required, Literal  # type: ignore

# ─────────────────────────────
# Aliases de base (stables)
# ─────────────────────────────

JSONValue = Any
JSONDict = Mapping[str, JSONValue]
JSONList = Sequence[JSONValue]

TenantId = str          # "tenant_*"
Scope = str             # ex.: "company", "glossary", "seo:title"
RefId = str             # ex.: "comp_1", "concept_42"
LocaleCode = str        # BCP-47: "fr", "pt-br"
SHA256Hex = str         # 64 hex chars
ModelName = str

Vector = Sequence[float]
Score = float

# ─────────────────────────────
# Énumérations (Literal)
# ─────────────────────────────

LLMProvider = Literal["mistral", "openai", "grok"]
LLMTask = Literal["translate", "summarize", "rerank", "generic"]
JobState = Literal["pending", "running", "done", "failed"]
Origin = Literal["human", "llm", "tm"]

# ─────────────────────────────
# Matching (API + interne)
# Aligné README_matching
# ─────────────────────────────

class MatchComponentScores(TypedDict, total=False):
    faiss: float
    pgvector: float
    lexical: float
    rerank: float

class MatchHit(TypedDict):
    ref_id: RefId
    score: Score
    components: MatchComponentScores
    meta: NotRequired[JSONDict]

class MatchExplanation(TypedDict, total=False):
    matched_terms: Sequence[str]
    components: MatchComponentScores
    notes: NotRequired[str]

class MatchFilters(TypedDict, total=False):
    """Filtres pour recherches hybrides dans matching (ex. : sector, region)."""
    sector: NotRequired[str]  # ex.: "aeronautique"
    region: NotRequired[str]  # ex.: "nord"
    lang: NotRequired[LocaleCode]  # ex.: "fr"
    custom: NotRequired[JSONDict]  # autres filtres dynamiques

class HybridSearchRequest(TypedDict, total=False):
    query: str
    tenant_id: TenantId
    scope: Scope
    top_k: int
    filters: MatchFilters
    lang: NotRequired[LocaleCode]

class HybridSearchResponse(TypedDict):
    results: Sequence[MatchHit]
    explanations: MatchExplanation

class UpsertEmbeddingItem(TypedDict):
    tenant_id: TenantId
    scope: Scope
    ref_id: RefId
    lang: LocaleCode
    text: str
    payload: NotRequired[JSONDict]

class EmbeddingDBItem(TypedDict):
    tenant_id: TenantId
    scope: Scope
    ref_id: RefId
    lang: LocaleCode
    model: ModelName
    dim: int
    checksum: SHA256Hex
    vector: Vector
    payload: NotRequired[JSONDict]

# ─────────────────────────────
# LLM_ai
# ─────────────────────────────

class ProviderInfo(TypedDict, total=False):
    provider: LLMProvider
    model: NotRequired[str]
    version: NotRequired[str]

class LLMEnrichTextRequest(TypedDict, total=False):
    text: str
    task: LLMTask
    lang: NotRequired[LocaleCode]
    tenant_id: NotRequired[TenantId]
    prompt_template: NotRequired[JSONDict]

class LLMEnrichTextResponse(TypedDict, total=False):
    text: str
    provider_info: NotRequired[ProviderInfo]
    alerts: NotRequired[Sequence[JSONDict]]

class LLMRerankItem(TypedDict):
    ref_id: RefId
    text: str
    score: NotRequired[Score]

class LLMEnrichRankingRequest(TypedDict, total=False):
    query: str
    items: Sequence[LLMRerankItem]
    tenant_id: NotRequired[TenantId]
    lang: NotRequired[LocaleCode]

class LLMEnrichRankingResult(TypedDict):
    ref_id: RefId
    score: Score

class LLMEnrichRankingResponse(TypedDict):
    results: Sequence[LLMEnrichRankingResult]
    provider_info: NotRequired[ProviderInfo]
    alerts: NotRequired[Sequence[JSONDict]]

# ─────────────────────────────
# Language
# ─────────────────────────────

class TranslationAlert(TypedDict):
    type: str
    field: str
    message: str

class TranslationPayload(TypedDict, total=False):
    key: str
    scope: Scope
    lang: LocaleCode
    text: str
    tenant_id: NotRequired[TenantId]
    version: NotRequired[int]
    alerts: NotRequired[Sequence[TranslationAlert]]
    embedding: NotRequired[Vector]
    source_checksum: SHA256Hex
    origin: Origin
    provider_info: NotRequired[ProviderInfo]
    domain: NotRequired[str]

class TranslationJobStats(TypedDict, total=False):
    processed: int
    per_lang: Mapping[LocaleCode, int]
    total_keys: NotRequired[int]
    translated: NotRequired[int]
    origin_breakdown: NotRequired[Mapping[str, int]]

class TranslationJobPayload(TypedDict, total=False):
    """Payload pour TranslationJob dans language (tasks.py, models.py)."""
    name: str
    state: JobState
    source_locale: LocaleCode
    target_locales: Sequence[LocaleCode]
    scope_filter: Sequence[str]
    stats: TranslationJobStats
    errors: Sequence[str]
    glossary_ids: Sequence[str]
    tenant_id: NotRequired[TenantId]
    priority: NotRequired[int]  # Priorité du job (ex. : 1=haute)
    created_at: NotRequired[str]  # ISO-8601 timestamp
    updated_at: NotRequired[str]  # ISO-8601 timestamp

# ─────────────────────────────
# Metrics (événements simples)
# ─────────────────────────────

class MetricEvent(TypedDict, total=False):
    name: str                  # ex.: "match.query.latency_ms"
    value: float
    dims: Mapping[str, str]    # ex.: {"tenant": "tenant_acme", "scope": "company"}
    ts_ms: NotRequired[int]

# ─────────────────────────────
# Export public (optionnel)
# ─────────────────────────────

__all__ = [
    # Aliases
    "JSONValue", "JSONDict", "JSONList", "TenantId", "Scope", "RefId",
    "LocaleCode", "SHA256Hex", "ModelName", "Vector", "Score",
    # Literals
    "LLMProvider", "LLMTask", "JobState", "Origin",
    # Matching
    "MatchComponentScores", "MatchHit", "MatchExplanation",
    "MatchFilters", "HybridSearchRequest", "HybridSearchResponse",
    "UpsertEmbeddingItem", "EmbeddingDBItem",
    # LLM_ai
    "LLMEnrichTextRequest", "LLMEnrichTextResponse",
    "LLMRerankItem", "LLMEnrichRankingRequest",
    "LLMEnrichRankingResult", "LLMEnrichRankingResponse",
    # Language
    "TranslationAlert", "ProviderInfo", "TranslationPayload",
    "TranslationJobStats", "TranslationJobPayload",
    # Metrics
    "MetricEvent",
]