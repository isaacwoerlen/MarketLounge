from typing import Callable, Type, Any, Optional
import tenacity
from functools import wraps

def retry_on_exception(
    exception_types: tuple[Type[Exception], ...] = (Exception,),
    max_attempts: int = 3,
    max_delay: Optional[float] = 3.0,
    timeout_per_attempt: Optional[float] = None,
) -> Callable:
    """Retries a function on specified exceptions with exponential backoff and optional per-attempt timeout.

    Args:
        exception_types: Tuple of exception types to catch and retry (default: (Exception,)).
        max_attempts: Maximum number of retry attempts (default: 3).
        max_delay: Maximum total delay in seconds for backoff (default: 3.0).
        timeout_per_attempt: Optional timeout in seconds for each attempt (default: None, no timeout).

    Returns:
        Callable: Decorated function that retries on specified exceptions.

    Raises:
        tenacity.RetryError: If max_attempts or max_delay is exceeded.
        TimeoutError: If timeout_per_attempt is set and an attempt exceeds it.

    Example:
        >>> @retry_on_exception(exception_types=(ValueError,), max_attempts=3, max_delay=3.0, timeout_per_attempt=1.0)
        ... def fetch_data(url: str) -> str:
        ...     # Some code that may raise ValueError
        ...     pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            retry_config = {
                "stop": tenacity.stop_after_attempt(max_attempts) | tenacity.stop_after_delay(max_delay),
                "wait": tenacity.wait_exponential(multiplier=0.5, max=2.0),
                "retry": tenacity.retry_if_exception_type(exception_types),
                "reraise": True,
            }
            if timeout_per_attempt is not None:
                retry_config["before_sleep"] = tenacity.before_sleep_log(
                    tenacity.logging.getLogger(__name__), tenacity.logging.WARNING
                )
                retry_config["stop"] = retry_config["stop"] | tenacity.stop_after_delay(timeout_per_attempt)
            retry = tenacity.Retrying(**retry_config)
            return retry(func, *args, **kwargs)
        return wrapper
    return decorator