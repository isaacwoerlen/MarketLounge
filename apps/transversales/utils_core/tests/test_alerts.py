import pytest
from utils_core.alerts import validate_alerts, merge_alerts
from utils_core.errors import AlertException

def test_merge_alerts_dedupe():
    """Teste la déduplication des alertes."""
    alerts = [
        [{"type": "seo", "field": "title", "message": "Too long"}],
        [{"type": "seo", "field": "title", "message": "Too long"}]
    ]
    result = merge_alerts(alerts, dedupe_on="type_field_message", prefer="last")
    assert len(result) == 1
    assert result[0] == {"type": "seo", "field": "title", "message": "Too long"}

def test_alert_exception_merge():
    """Teste AlertException avec merge_alerts."""
    alerts = [
        {"type": "seo", "field": "title", "message": "Too long"},
        {"type": "seo", "field": "title", "message": "Too long"}
    ]
    exc = AlertException("Validation failed", alerts=alerts)
    assert len(exc.alerts) == 1
    assert exc.alerts[0]["type"] == "seo"