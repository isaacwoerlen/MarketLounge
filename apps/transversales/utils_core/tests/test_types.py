import pytest
from utils_core.types import MatchFilters, TranslationJobPayload

def test_match_filters():
    """Teste le typage de MatchFilters."""
    filters: MatchFilters = {"sector": "aeronautique", "region": "nord", "lang": "fr"}
    assert filters["sector"] == "aeronautique"
    assert filters.get("custom") is None  # Champ optionnel

def test_translation_job_payload():
    """Teste le typage de TranslationJobPayload."""
    job: TranslationJobPayload = {
        "name": "batch_1",
        "state": "pending",
        "source_locale": "fr",
        "target_locales": ["en", "es"],
        "scope_filter": ["seo:title"],
        "stats": {"processed": 10, "per_lang": {"en": 5, "es": 5}},
        "errors": [],
        "glossary_ids": ["gloss_1"],
        "tenant_id": "tenant_123",
        "priority": 1,
    }
    assert job["state"] == "pending"
    assert job["stats"]["processed"] == 10