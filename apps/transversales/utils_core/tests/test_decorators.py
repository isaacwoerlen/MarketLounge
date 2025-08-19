import pytest
import time
from unittest.mock import patch, Mock
from utils_core.decorators import retry_on_exception
from utils_core.errors import RetryableError

def test_retry_on_exception_success():
    """Test that retry_on_exception succeeds on first attempt."""
    @retry_on_exception(exception_types=(ValueError,), max_attempts=3, max_delay=3.0)
    def success_func():
        return "success"
    
    result = success_func()
    assert result == "success"

def test_retry_on_exception_retries_success():
    """Test that retry_on_exception retries and succeeds after failures."""
    call_count = 0
    def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RetryableError("Temporary failure")
        return "success"
    
    decorated_func = retry_on_exception(exception_types=(RetryableError,), max_attempts=3, max_delay=3.0)(flaky_func)
    result = decorated_func()
    assert result == "success"
    assert call_count == 3

def test_retry_on_exception_exceeds_max_attempts():
    """Test that retry_on_exception raises error after max attempts."""
    def failing_func():
        raise RetryableError("Persistent failure")
    
    decorated_func = retry_on_exception(exception_types=(RetryableError,), max_attempts=2, max_delay=3.0)(failing_func)
    with pytest.raises(RetryableError, match="Persistent failure"):
        decorated_func()

def test_retry_on_exception_respects_max_delay():
    """Test that retry_on_exception respects max_delay limit."""
    def slow_func():
        time.sleep(1)
        raise RetryableError("Slow failure")
    
    decorated_func = retry_on_exception(exception_types=(RetryableError,), max_attempts=5, max_delay=2.0)(slow_func)
    start_time = time.time()
    with pytest.raises(RetryableError):
        decorated_func()
    elapsed = time.time() - start_time
    assert elapsed < 2.5  # Allow some buffer for execution overhead

def test_retry_on_exception_unhandled_exception():
    """Test that retry_on_exception does not retry unhandled exceptions."""
    def wrong_exception_func():
        raise ValueError("Wrong exception")
    
    decorated_func = retry_on_exception(exception_types=(RetryableError,), max_attempts=3, max_delay=3.0)(wrong_exception_func)
    with pytest.raises(ValueError, match="Wrong exception"):
        decorated_func()

def test_retry_on_exception_timeout_per_attempt():
    """Test that retry_on_exception respects timeout_per_attempt."""
    def slow_func():
        time.sleep(0.5)
        raise RetryableError("Slow failure")
    
    decorated_func = retry_on_exception(
        exception_types=(RetryableError,), max_attempts=3, max_delay=3.0, timeout_per_attempt=0.2
    )(slow_func)
    start_time = time.time()
    with pytest.raises(RetryableError):
        decorated_func()
    elapsed = time.time() - start_time
    assert elapsed < 0.5  # Should fail after one attempt due to timeout

@patch("utils_core.decorators.time.perf_counter")
def test_retry_on_exception_with_mock(mock_perf_counter):
    """Test retry_on_exception with mocked timing for deterministic testing."""
    mock_perf_counter.side_effect = [0, 0.1, 0.2, 0.3]  # Simulate time progression
    call_count = 0
    def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RetryableError("Temporary failure")
        return "success"
    
    decorated_func = retry_on_exception(
        exception_types=(RetryableError,), max_attempts=3, max_delay=3.0, timeout_per_attempt=0.5
    )(flaky_func)
    result = decorated_func()
    assert result == "success"
    assert call_count == 2