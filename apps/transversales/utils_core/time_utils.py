from datetime import datetime, timezone
from typing import Iterator
from contextlib import contextmanager
import time
from dataclasses import dataclass

@dataclass
class Timer:
    """A context manager to measure elapsed time."""
    start: float = 0.0
    elapsed_ms: float = 0.0

@contextmanager
def timer() -> Iterator[Timer]:
    """Context manager to measure elapsed time in milliseconds.

    Yields:
        Timer: An object with start time and elapsed time in milliseconds.

    Example:
        with timer() as t:
            time.sleep(1)
        print(f"Operation took {t.elapsed_ms}ms")
    """
    t = Timer(start=time.perf_counter())
    yield t
    t.elapsed_ms = (time.perf_counter() - t.start) * 1000

def utc_now() -> datetime:
    """Return the current UTC datetime with timezone info.

    Returns:
        datetime: Current UTC datetime.
    """
    return datetime.now(timezone.utc)

def timestamp_ms() -> int:
    """Return the current timestamp in milliseconds.

    Returns:
        int: Current timestamp in milliseconds since epoch.
    """
    return int(time.time() * 1000)

def format_duration(seconds: float) -> str:
    """Format duration in seconds to a human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        str: Formatted duration (e.g., '1h 30m 45s').
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs:.2f}s")
    return " ".join(parts)

def parse_iso8601(iso_str: str) -> datetime:
    """Parse an ISO 8601 string to a datetime object.

    Args:
        iso_str: ISO 8601 formatted string (e.g., '2023-10-01T12:00:00Z').

    Returns:
        datetime: Parsed datetime object.

    Raises:
        ValueError: If the string is not a valid ISO 8601 format.
    """
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError(f"Invalid ISO 8601 format: {iso_str}") from e