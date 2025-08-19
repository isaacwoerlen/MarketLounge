import pytest
from unittest.mock import patch, Mock
import json
import logging
from utils_core.metrics import (
    format_tags,
    log_metric,
    record_metric_wrapper,
    METRIC_MATCH_QUERY_LATENCY,
)
from utils_core.errors import ValidationError

def test_format_tags_without_tenant_id():
    """Test format_tags without tenant_id."""
    tags = {"operation": "search", "scope": "company"}
    result = format_tags(tags)
    assert result == "operation=search,scope=company"
    result_dict = format_tags(tags, as_string=False)
    assert result_dict == {"operation": "search", "scope": "company"}

def test_format_tags_with_tenant_id():
    """Test format_tags with valid tenant_id."""
    tags = {"operation": "search"}
    result = format_tags(tags, tenant_id="tenant_123")
    assert result == "operation=search,tenant_id=tenant_123"
    result_dict = format_tags(tags, tenant_id="tenant_123", as_string=False)
    assert result_dict == {"operation": "search", "tenant_id": "tenant_123"}

def test_format_tags_invalid_tenant_id():
    """Test format_tags raises ValidationError for invalid tenant_id."""
    with pytest.raises(ValidationError, match="Invalid tenant_id"):
        format_tags({"operation": "search"}, tenant_id="invalid@tenant")

def test_format_tags_cleaning():
    """Test format_tags cleans keys and values."""
    tags = {"Invalid Key!": "Value,With,Commas\n"}
    result = format_tags(tags)
    assert result == "invalid_key=value_with_commas_"

@patch("utils_core.metrics._statsd_client")
@patch("utils_core.metrics._sink")
@patch("logging.Logger.info")
def test_log_metric_basic(mock_logger, mock_sink, mock_statsd):
    """Test log_metric without tenant_id."""
    mock_statsd.gauge = Mock()
    log_metric(METRIC_MATCH_QUERY_LATENCY, 150.5, tags={"scope": "company"})
    mock_logger.assert_called_once()
    payload = json.loads(mock_logger.call_args[0][0])
    assert payload["name"] == METRIC_MATCH_QUERY_LATENCY
    assert payload["value"] == 150.5
    assert payload["tags"] == {"scope": "company"}
    assert isinstance(payload["ts_ms"], int)
    if mock_statsd:
        mock_statsd.gauge.assert_called_with(
            METRIC_MATCH_QUERY_LATENCY.replace(".", "_"),
            150.5,
            tags=["scope:company"]
        )
    if mock_sink:
        mock_sink.assert_called_with(
            METRIC_MATCH_QUERY_LATENCY,
            150.5,
            {"scope": "company"},
            payload["ts_ms"]
        )

@patch("utils_core.metrics._statsd_client")
@patch("utils_core.metrics._sink")
@patch("logging.Logger.info")
def test_log_metric_with_tenant_id(mock_logger, mock_sink, mock_statsd):
    """Test log_metric with tenant_id."""
    mock_statsd.gauge = Mock()
    log_metric(METRIC_MATCH_QUERY_LATENCY, 150.5, tags={"scope": "company"}, tenant_id="tenant_123")
    mock_logger.assert_called_once()
    payload = json.loads(mock_logger.call_args[0][0])
    assert payload["name"] == METRIC_MATCH_QUERY_LATENCY
    assert payload["value"] == 150.5
    assert payload["tags"] == {"scope": "company", "tenant_id": "tenant_123"}
    if mock_statsd:
        mock_statsd.gauge.assert_called_with(
            METRIC_MATCH_QUERY_LATENCY.replace(".", "_"),
            150.5,
            tags=["scope:company", "tenant_id:tenant_123"]
        )
    if mock_sink:
        mock_sink.assert_called_with(
            METRIC_MATCH_QUERY_LATENCY,
            150.5,
            {"scope": "company", "tenant_id": "tenant_123"},
            payload["ts_ms"]
        )

def test_log_metric_invalid_value():
    """Test log_metric raises TypeError for non-numeric value."""
    with pytest.raises(TypeError, match="value must be numeric"):
        log_metric(METRIC_MATCH_QUERY_LATENCY, "invalid")

@patch("utils_core.metrics._statsd_client")
@patch("utils_core.metrics._sink")
@patch("utils_core.metrics.timer")
def test_record_metric_wrapper_success(mock_timer, mock_sink, mock_statsd):
    """Test record_metric_wrapper on successful function execution."""
    mock_statsd.gauge = Mock()
    mock_timer.return_value.__enter__.return_value.elapsed_ms = 100.0

    @record_metric_wrapper("test_func", static_tags={"operation": "batch"}, tenant_id="tenant_123")
    def test_func():
        return "success"

    result = test_func()
    assert result == "success"
    assert mock_statsd.gauge.call_args_list == [
        call("test_func_latency_ms", 100.0, tags=["operation:batch", "tenant_id:tenant_123"]),
        call("test_func_success", 1, tags=["operation:batch", "tenant_id:tenant_123"]),
    ]
    assert mock_sink.call_count == 2
    _, kwargs = mock_sink.call_args_list[0]
    assert kwargs["name"] == "test_func_latency_ms"
    assert kwargs["value"] == 100.0
    assert kwargs["tags"] == {"operation": "batch", "tenant_id": "tenant_123"}

@patch("utils_core.metrics._statsd_client")
@patch("utils_core.metrics._sink")
@patch("utils_core.metrics.timer")
def test_record_metric_wrapper_failure(mock_timer, mock_sink, mock_statsd):
    """Test record_metric_wrapper on function failure."""
    mock_statsd.gauge = Mock()
    mock_timer.return_value.__enter__.return_value.elapsed_ms = 100.0

    @record_metric_wrapper("test_func", static_tags={"operation": "batch"}, tenant_id="tenant_123")
    def test_func():
        raise ValueError("Failure")

    with pytest.raises(ValueError, match="Failure"):
        test_func()
    assert mock_statsd.gauge.call_args_list == [
        call("test_func_latency_ms", 100.0, tags=["operation:batch", "tenant_id:tenant_123"]),
        call("test_func_error", 1, tags=["operation:batch", "tenant_id:tenant_123"]),
    ]
    assert mock_sink.call_count == 2
    _, kwargs = mock_sink.call_args_list[1]
    assert kwargs["name"] == "test_func_error"
    assert kwargs["value"] == 1
    assert kwargs["tags"] == {"operation": "batch", "tenant_id": "tenant_123"}

@patch("utils_core.metrics._statsd_client")
@patch("utils_core.metrics._sink")
@patch("utils_core.metrics.timer")
def test_record_metric_wrapper_dynamic_tags(mock_timer, mock_sink, mock_statsd):
    """Test record_metric_wrapper with dynamic tags."""
    mock_statsd.gauge = Mock()
    mock_timer.return_value.__enter__.return_value.elapsed_ms = 100.0

    @record_metric_wrapper("test_func", static_tags={"operation": "batch"}, 
                          dynamic_tags=lambda: {"scope": "company"}, tenant_id="tenant_123")
    def test_func():
        return "success"

    result = test_func()
    assert result == "success"
    assert mock_statsd.gauge.call_args_list == [
        call("test_func_latency_ms", 100.0, tags=["operation:batch", "scope:company", "tenant_id:tenant_123"]),
        call("test_func_success", 1, tags=["operation:batch", "scope:company", "tenant_id:tenant_123"]),
    ]