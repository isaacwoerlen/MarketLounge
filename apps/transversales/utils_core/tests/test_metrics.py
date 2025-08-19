import pytest
from utils_core.metrics import log_metric, record_metric_wrapper, METRIC_MATCH_DIRTY_RATIO
from utils_core.constants import METRIC_MATCH_DIRTY_RATIO

def test_record_metric_wrapper_nominal():
    """Teste record_metric_wrapper avec succès."""
    @record_metric_wrapper('test.operation', static_tags={'env': 'test'},
                           dynamic_tags=lambda: {'tenant_id': 'tenant_123'})
    def success_func():
        return "success"
    result = success_func()
    assert result == "success"

def test_record_metric_wrapper_error():
    """Teste record_metric_wrapper avec erreur."""
    @record_metric_wrapper('test.operation', static_tags={'env': 'test'})
    def error_func():
        raise ValueError("Test error")
    with pytest.raises(ValueError, match="Test error"):
        error_func()

def test_log_metric_dirty_ratio():
    """Teste METRIC_MATCH_DIRTY_RATIO."""
    log_metric(METRIC_MATCH_DIRTY_RATIO, 0.05, tags={'tenant_id': 'tenant_123', 'scope': 'company'})
    # Vérification via logger mock dans un vrai test