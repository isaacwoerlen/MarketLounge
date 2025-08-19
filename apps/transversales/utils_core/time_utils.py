# utils_core/time_utils.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

__all__ = ["utc_now", "timestamp_ms", "format_duration", "parse_iso8601"]


# ──────────────────────────────────────────────────────────────────────────────
# Basics
# ──────────────────────────────────────────────────────────────────────────────

def utc_now() -> datetime:
    """
    Datetime 'aware' en UTC (précis à la microseconde).
    """
    return datetime.now(timezone.utc)


def timestamp_ms(dt: Optional[datetime] = None) -> int:
    """
    Millisecondes depuis l'époque UNIX.
    - Si dt=None → now (UTC).
    - Si dt est naïf → assumé UTC.
    """
    d = dt or utc_now()
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    else:
        d = d.astimezone(timezone.utc)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return int((d - epoch).total_seconds() * 1000)


# ──────────────────────────────────────────────────────────────────────────────
# Formatting
# ──────────────────────────────────────────────────────────────────────────────

def _total_seconds(value: Union[float, int, timedelta]) -> float:
    if isinstance(value, timedelta):
        return value.total_seconds()
    return float(value)

def format_duration(
    value: Union[float, int, timedelta],
    *,
    precision: int = 2,
    short: bool = False,
) -> str:
    """
    Formate une durée de façon lisible.
    Règles:
      - ≥ 1h  → 'Hh Mm Ss' (omit composants nuls, s avec décimales)
      - ≥ 1m  → 'Mm Ss'
      - ≥ 1s  → 'S.s s'
      - ≥ 1ms → 'X ms'
      - sinon → 'X µs'
    Args:
        value: secondes (float/int) ou timedelta.
        precision: décimales pour la partie secondes.
        short: si True, sans espaces ('1h2m3.45s' au lieu de '1h 2m 3.45s').
    """
    secs = _total_seconds(value)
    sign = "-" if secs < 0 else ""
    s = abs(secs)

    sep = "" if short else " "
    parts: list[str] = []

    if s >= 3600:
        h = int(s // 3600)
        s -= h * 3600
        m = int(s // 60)
        s -= m * 60
        if h:
            parts.append(f"{h}h")
        if m:
            parts.append(f"{m}m")
        parts.append(f"{s:.{precision}f}s" if precision > 0 else f"{int(round(s))}s")
        return sign + sep.join(parts)

    if s >= 60:
        m = int(s // 60)
        s -= m * 60
        parts.append(f"{m}m")
        parts.append(f"{s:.{precision}f}s" if precision > 0 else f"{int(round(s))}s")
        return sign + sep.join(parts)

    if s >= 1:
        return sign + (f"{s:.{precision}f}s" if precision > 0 else f"{int(round(s))}s")

    # < 1s → ms / µs
    ms = s * 1_000
    if ms >= 1:
        # éviter -0.00
        val = f"{ms:.{max(0, precision)}f}".rstrip("0").rstrip(".")
        return f"{sign}{val}{'' if short else ' '}ms"

    us = s * 1_000_000
    val = f"{us:.0f}"
    return f"{sign}{val}{'' if short else ' '}µs"


# ──────────────────────────────────────────────────────────────────────────────
# Parsing
# ──────────────────────────────────────────────────────────────────────────────

def parse_iso8601(
    value: Union[str, datetime, int, float],
    *,
    default_tz: timezone = timezone.utc,
    naive_policy: str = "assume_utc",  # "assume_utc" | "attach_default" | "error"
) -> datetime:
    """
    Parse ISO-8601 (tolérant) → datetime *aware*.
    Accepte:
      - str: '2025-08-18T10:15:30Z', '2025-08-18 10:15:30+02:00', '2025-08-18T10:15:30.123456'
      - datetime: si naïf → selon naive_policy
      - int/float: timestamp (secondes UNIX)

    naive_policy:
      - "assume_utc"   → naïf interprété comme UTC (replace tzinfo=UTC)
      - "attach_default" → attache default_tz sans conversion
      - "error"        → lève ValueError si naïf
    """
    # datetime direct
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            if naive_policy == "assume_utc":
                return dt.replace(tzinfo=timezone.utc)
            if naive_policy == "attach_default":
                return dt.replace(tzinfo=default_tz)
            raise ValueError("Naive datetime not allowed (naive_policy='error').")
        return dt.astimezone(default_tz) if default_tz else dt

    # timestamp numérique (secondes)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)

    s = str(value).strip()
    if not s:
        raise ValueError("Empty ISO-8601 string")

    # Support 'Z' → '+00:00'
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1] + "+00:00"

    # Autoriser espace comme séparateur date/heure
    s = s.replace(" ", "T", 1) if " " in s and "T" not in s else s

    try:
        dt = datetime.fromisoformat(s)
    except Exception as e:
        raise ValueError(f"Invalid ISO-8601 datetime: {value!r} ({e})")

    if dt.tzinfo is None:
        if naive_policy == "assume_utc":
            dt = dt.replace(tzinfo=timezone.utc)
        elif naive_policy == "attach_default":
            dt = dt.replace(tzinfo=default_tz)
        else:
            raise ValueError("Naive datetime not allowed (naive_policy='error').")
    return dt
