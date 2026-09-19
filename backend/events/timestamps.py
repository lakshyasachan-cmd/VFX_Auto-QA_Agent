"""
Robust timestamp parsing and normalization utilities for VFX events.
Ensures all timestamps are strictly timezone-aware UTC.
"""

from datetime import datetime, timezone
from typing import Any, Optional
import dateutil.parser


def now_utc() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def format_iso8601_utc(dt: datetime) -> str:
    """Format datetime as canonical ISO-8601 UTC string (ending in Z)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    # Use ISO format ending in Z
    iso_str = dt.isoformat()
    if iso_str.endswith("+00:00"):
        iso_str = iso_str[:-6] + "Z"
    elif not iso_str.endswith("Z"):
        iso_str += "Z"
    return iso_str


def parse_timestamp(value: Optional[Any]) -> datetime:
    """
    Parse a raw timestamp into a timezone-aware UTC datetime.
    Supports:
    - datetime objects (naive or aware)
    - ISO-8601 / RFC-3339 strings
    - Unix epoch timestamps (seconds or milliseconds as int/float/str)
    - None / empty string -> returns current UTC time.
    """
    if value is None or value == "":
        return now_utc()

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    # Check for epoch numeric timestamp
    if isinstance(value, (int, float)):
        # If timestamp is likely milliseconds (> 10^11)
        if value > 1e11:
            value = value / 1000.0
        return datetime.fromtimestamp(value, tz=timezone.utc)

    if isinstance(value, str):
        v = value.strip()
        # Check if numeric string
        try:
            num = float(v)
            if num > 1e11:
                num = num / 1000.0
            return datetime.fromtimestamp(num, tz=timezone.utc)
        except ValueError:
            pass

        try:
            parsed = dateutil.parser.parse(v)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            else:
                parsed = parsed.astimezone(timezone.utc)
            return parsed
        except (ValueError, OverflowError) as exc:
            raise ValueError(f"Unparseable timestamp format: '{value}'") from exc

    raise ValueError(f"Unsupported timestamp type: {type(value)} ({value})")
