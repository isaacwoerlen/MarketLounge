# tests/test_utils_core/test_integration.py
import pytest
from unittest.mock import Mock
from django.core.exceptions import ValidationError
from utils_core.utils import compute_checksum, retry_on_exception
from utils_core.validators import normalize_locale, validate_lang, validate_tenant_id, validate_json_field
from utils_core.text_cleaning import normalize_text
from utils_core.metrics import record_metric_wrapper, log_metric
from utils_core.alerts import validate_alerts, merge_alerts
from utils_core.errors import AlertException
from utils_core.env import get_env_variable
from utils_core.constants import METRIC_MATCH_DIRTY_RATIO

# Fixtures pour mocker les modèles et services
@pytest.fixture
def mock_language_models():
    """Mock pour language.models.Translation et TranslatableKey."""
    class MockTranslation:
        def __init__(self, source_text, source_checksum):
            self.source_text = source_text
            self.source_checksum = source_checksum
            self.tenant_id = "tenant_123"
            self.lang = "fr"

        def full_clean(self):
            validate_tenant_id(self.tenant_id)
            validate_lang(self.lang)
            validate_checksum(self.source_checksum)

    class MockTranslatableKey:
        def __init__(self, key, scope):
            self.key = key
            self.scope = scope

    return MockTranslation, MockTranslatableKey

@pytest.fixture
def mock_matching_models():
    """Mock pour matching.models.EmbeddingItem."""
    class MockEmbeddingItem:
        def __init__(self, text, tenant_id, scope, ref_id, lang):
            self.text = text
            self.tenant_id = tenant_id
            self.scope = scope
            self.ref_id = ref_id
            self.lang = lang
            self.checksum = compute_checksum(text)

        def full_clean(self):
            validate_tenant_id(self.tenant_id)
            validate_scope(self.scope)
            validate_lang(self.lang)
            validate_checksum(self.checksum)

    return MockEmbeddingItem

@pytest.fixture
def mock_language_service():
    """Mock pour language.services.batch_translate_scope."""
    def batch_translate_scope(scope, source_lang, target_langs, tenant_id=None):
        normalized_text = normalize_text("Soudure inox 316L", remove_accents_flag=True)
        checksum = compute_checksum(normalized_text)
        return {"processed": 1, "per_lang": {target_langs[0]: 1}, "errors": []}

    return Mock(side_effect=batch_translate_scope)

@pytest.fixture
def mock_matching_service():
    """Mock pour matching.services.hybrid_search."""
    def hybrid_search(query, tenant_id, scope, top_k, filters, lang):
        normalized_query = normalize_text(query, remove_accents_flag=True)
        return [{"ref_id": "comp_1", "score": 0.95, "components": {"faiss": 0.5}}]

    return Mock(side_effect=hybrid_search)

# Tests intégrés
def test_integration_language_translation(mock_language_models):
    """Teste l'intégration de compute_checksum, normalize_locale, et validate_lang dans language."""
    MockTranslation, MockTranslatableKey = mock_language_models
    source_text = "Soudure inox 316L"
    normalized_lang = normalize_locale("fr_FR")
    checksum = compute_checksum(source_text)
    
    translation = MockTranslation(source_text, checksum)
    translation.lang = normalized_lang
    
    # Valider les champs
    translation.full_clean()  # Ne doit pas lever d'erreur
    assert translation.source_checksum == checksum
    assert translation.lang == "fr-fr"

def test_integration_matching_query(mock_matching_models, mock_matching_service):
    """Teste l'intégration de normalize_text, validate_tenant_id, et record_metric_wrapper dans matching."""
    MockEmbeddingItem = mock_matching_models
    query = "<p>Soudure Inox 316L aéronautique</p>"
    tenant_id = "tenant_123"
    scope = "company"
    
    # Normaliser la query
    normalized_query = normalize_text(query, remove_accents_flag=True)
    assert normalized_query == "soudure inox 316l aeronautique"
    
    # Créer un item mock
    item = MockEmbeddingItem(normalized_query, tenant_id, scope, "comp_1", "fr")
    item.full_clean()  # Ne doit pas lever d'erreur
    
    # Instrumenter la recherche
    @record_metric_wrapper('match.hybrid_search', static_tags={'scope': scope})
    def wrapped_search():
        return mock_matching_service(normalized_query, tenant_id, scope, 10, {}, "fr")
    
    result = wrapped_search()
    assert len(result) == 1
    assert result[0]["ref_id"] == "comp_1"

def test_integration_alerts_seo(mock_language_service):
    """Teste l'intégration de validate_alerts et AlertException pour SEO dans language."""
    alerts = [{"type": "seo", "field": "title", "message": "Too long"}]
    validated_alerts = validate_alerts(alerts)
    
    try:
        raise AlertException("SEO validation failed", alerts=alerts)
    except AlertException as e:
        assert len(e.alerts) == 1
        assert e.alerts[0]["type"] == "seo"
    
    # Simuler fusion d'alertes
    merged = merge_alerts([alerts, alerts], dedupe_on="type_field_message", prefer="last")
    assert len(merged) == 1

def test_integration_env_config():
    """Teste l'intégration de get_env_variable pour configs partagées."""
    import os
    os.environ["TEST_EMBEDDING_DIM"] = "512"
    dim = get_env_variable("TEST_EMBEDDING_DIM", cast="int", default=384)
    assert dim == 512
    
    os.environ["TEST_LLM_TIMEOUT"] = "10.0"
    timeout = get_env_variable("TEST_LLM_TIMEOUT", cast="float", default=5.0)
    assert timeout == 10.0

def test_integration_retry_on_exception(mock_language_service):
    """Teste retry_on_exception avec un service mocké."""
    @retry_on_exception(exception_types=ValueError, max_attempts=2)
    def failing_service():
        raise ValueError("Test retry")
    
    with pytest.raises(ValueError, match="Test retry"):
        failing_service()