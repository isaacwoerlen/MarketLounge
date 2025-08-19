import pytest
from unittest.mock import patch, Mock
import time
from utils_core.utils import compute_checksum, slugify, normalize_text
from utils_core import timer, retry_on_exception, log_metric

def test_compute_checksum_sha256():
    """Test that compute_checksum generates correct SHA256 hash."""
    text = "Soudure inox 316L"
    expected = "0e9c3f4f6b7a8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3"
    assert compute_checksum(text) == expected

def test_compute_checksum_unsupported_algo():
    """Test that compute_checksum raises error for unsupported algorithm."""
    with pytest.raises(ValueError, match="Unsupported algorithm: md5"):
        compute_checksum("test", algo="md5")

def test_slugify_basic():
    """Test that slugify converts text to URL-safe slug."""
    assert slugify("Soudure Inox 316L") == "soudure-inox-316l"
    assert slugify("Test  Case!") == "test-case"
    assert slugify("  Multiple   Spaces  ") == "multiple-spaces"

def test_slugify_special_chars():
    """Test slugify with special characters."""
    assert slugify("Hello@World#2025") == "hello-world-2025"
    assert slugify("---") == ""

def test_slugify_empty():
    """Test slugify with empty or whitespace-only input."""
    assert slugify("") == ""
    assert slugify("   ") == ""

def test_normalize_text_reexport():
    """Test that normalize_text is correctly re-exported from text_cleaning."""
    text = "<p>Soudure  Inox  316L!</p>"
    expected = "soudure inox 316l"
    assert normalize_text(text, remove_accents_flag=True) == expected

def test_reexport_timer():
    """Test that timer is correctly re-exported from time_utils via __init__."""
    with timer() as t:
        assert isinstance(t.start, float)
        assert t.elapsed_ms == 0.0
        time.sleep(0.1)
    assert t.elapsed_ms > 90  # Allow some variance
    assert t.elapsed_ms < 150

def test_reexport_retry_on_exception():
    """Test that retry_on_exception is correctly re-exported from decorators via __init__."""
    call_count = 0
    @retry_on_exception(exception_types=(ValueError,), max_attempts=2, max_delay=1.0)
    def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ValueError("Temporary failure")
        return "success"
    
    result = flaky_func()
    assert result == "success"
    assert call_count == 2

@patch("utils_core.metrics._statsd_client")
@patch("utils_core.metrics._sink")
@patch("logging.Logger.info")
def test_reexport_log_metric(mock_logger, mock_sink, mock_statsd):
    """Test that log_metric is correctly re-exported from metrics via __init__."""
    mock_statsd.gauge = Mock()
    log_metric("test_metric", 150.5, tags={"scope": "company"}, tenant_id="tenant_123")
    mock_logger.assert_called_once()
    payload = json.loads(mock_logger.call_args[0][0])
    assert payload["name"] == "test_metric"
    assert payload["value"] == 150.5
    assert payload["tags"] == {"scope": "company", "tenant_id": "tenant_123"}
    if mock_statsd:
        mock_statsd.gauge.assert_called_with(
            "test_metric",
            150.5,
            tags=["scope:company", "tenant_id:tenant_123"]
        )
    if mock_sink:
        mock_sink.assert_called_with(
            "test_metric",
            150.5,
            {"scope": "company", "tenant_id": "tenant_123"},
            payload["ts_ms"]
        )