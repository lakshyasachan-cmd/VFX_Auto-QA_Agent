"""
Unit tests for timestamp parsing and UTC formatting.
"""

from datetime import datetime, timezone
import pytest
from backend.events.timestamps import format_iso8601_utc, now_utc, parse_timestamp


def test_parse_none_or_empty_returns_now():
    ts = parse_timestamp(None)
    assert ts.tzinfo is not None
    assert ts.tzinfo == timezone.utc

    ts2 = parse_timestamp("")
    assert ts2.tzinfo == timezone.utc


def test_parse_iso8601_string():
    ts = parse_timestamp("2026-09-08T16:45:00Z")
    assert ts == datetime(2026, 9, 8, 16, 45, 0, tzinfo=timezone.utc)
    assert format_iso8601_utc(ts) == "2026-09-08T16:45:00Z"


def test_parse_iso8601_offset():
    # Offset +05:30 -> converted to UTC
    ts = parse_timestamp("2026-09-08T22:15:00+05:30")
    assert ts.tzinfo == timezone.utc
    assert ts.hour == 16
    assert ts.minute == 45


def test_parse_unix_epoch_seconds():
    # 1700000000 = Tue Nov 14 2023 22:13:20 UTC
    ts = parse_timestamp(1700000000)
    assert ts == datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)


def test_parse_unix_epoch_milliseconds():
    # 1700000000000
    ts = parse_timestamp(1700000000000)
    assert ts == datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)


def test_parse_invalid_string_raises():
    with pytest.raises(ValueError, match="Unparseable timestamp format"):
        parse_timestamp("not-a-valid-date-string-xyz")
