import pytest
import time
from datetime import datetime, timezone
from utils_core.time_utils import timer, utc_now, timestamp_ms, format_duration, parse_iso8601

def test_timer_measures_elapsed_time():
    """Test that timer measures elapsed time correctly."""
    with timer() as t:
        time.sleep(0.1)  # Simulate work
    assert t.elapsed_ms > 90  # Allow some variance
    assert t.elapsed_ms < 150
    assert isinstance(t.start, float)
    assert isinstance(t.elapsed_ms, float)

def test_utc_now_returns_utc_datetime():
    """Test that utc_now returns a UTC datetime with timezone."""
    result = utc_now()
    assert isinstance(result, datetime)
    assert result.tzinfo == timezone.utc

def test_timestamp_ms_returns_milliseconds():
    """Test that timestamp_ms returns current time in milliseconds."""
    result = timestamp_ms()
    expected = int(time.time() * 1000)
    assert isinstance(result, int)
    assert abs(result - expected) < 1000  # Allow 1s variance

def test_format_duration_formats_correctly():
    """Test that format_duration formats seconds into human-readable string."""
    assert format_duration(3665.5) == "1h 1m 5.50s"
    assert format_duration(90) == "1m 30.00s"
    assert format_duration(0.5) == "0.50s"
    assert format_duration(0) == "0.00s"

def test_parse_iso8601_parses_valid_format():
    """Test that parse_iso8601 parses valid ISO 8601 strings."""
    result = parse_iso8601("2023-10-01T12:00:00Z")
    assert isinstance(result, datetime)
    assert result == datetime(2023, 10, 1, 12, 0, 0, tzinfo=timezone.utc)

def test_parse_iso8601_raises_invalid_format():
    """Test that parse_iso8601 raises ValueError for invalid formats."""
    with pytest.raises(ValueError, match="Invalid ISO 8601 format"):
        parse_iso8601("invalid-date")

def test_timer_with_no_work():
    """Test timer with minimal work."""
    with timer() as t:
        pass
    assert t.elapsed_ms < 10  # Should be very small