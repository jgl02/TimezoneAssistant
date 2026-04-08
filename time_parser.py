import re
from datetime import datetime, timedelta
import pytz

# Mapping of common abbreviations → pytz timezone string
TZ_ABBREVIATIONS: dict[str, str] = {
    "PT":   "US/Pacific",
    "PST":  "US/Pacific",
    "PDT":  "US/Pacific",
    "MT":   "US/Mountain",
    "MST":  "US/Mountain",
    "MDT":  "US/Mountain",
    "CT":   "US/Central",
    "CST":  "US/Central",
    "CDT":  "US/Central",
    "ET":   "US/Eastern",
    "EST":  "US/Eastern",
    "EDT":  "US/Eastern",
    "AT":   "America/Halifax",
    "AST":  "America/Halifax",
    "ADT":  "America/Halifax",
    "AKT":  "America/Anchorage",
    "AKST": "America/Anchorage",
    "AKDT": "America/Anchorage",
    "HT":   "Pacific/Honolulu",
    "HST":  "Pacific/Honolulu",
    "GMT":  "UTC",
    "UTC":  "UTC",
    "BST":  "Europe/London",
    "WET":  "Europe/London",
    "CET":  "Europe/Paris",
    "CEST": "Europe/Paris",
    "GST":  "Asia/Dubai",
    "IST":  "Asia/Kolkata",
    "JST":  "Asia/Tokyo",
    "AEST": "Australia/Sydney",
    "AEDT": "Australia/Sydney",
}

# Optional trailing timezone abbreviation, e.g. " EST", " CST"
_TZ_SUFFIX = r"(?:\s+([A-Z]{2,5}))?"

# 12hr: "2pm", "2:30pm", "2 PM EST"
_12HR = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)" + _TZ_SUFFIX,
    re.IGNORECASE,
)
# 24hr: "14:00", "14:00 CST"
_24HR = re.compile(
    r"\b([01]?\d|2[0-3]):([0-5]\d)" + _TZ_SUFFIX,
)


def _resolve_tz(abbr: str | None) -> pytz.BaseTzInfo | None:
    if not abbr:
        return None
    return pytz.timezone(TZ_ABBREVIATIONS[abbr.upper()]) if abbr.upper() in TZ_ABBREVIATIONS else None


def find_times(content: str) -> list[tuple[int, int, pytz.BaseTzInfo | None]]:
    """Return a list of (hour24, minute, inline_tz_or_None) tuples found in the message."""
    results = []
    seen = set()

    for m in _12HR.finditer(content):
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        meridiem = m.group(3).lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        inline_tz = _resolve_tz(m.group(4))
        key = (hour, minute)
        if key not in seen:
            seen.add(key)
            results.append((hour, minute, inline_tz))

    if not results:
        for m in _24HR.finditer(content):
            hour = int(m.group(1))
            minute = int(m.group(2))
            inline_tz = _resolve_tz(m.group(3))
            key = (hour, minute)
            if key not in seen:
                seen.add(key)
                results.append((hour, minute, inline_tz))

    return results


def to_unix_timestamp(hour: int, minute: int, tz: pytz.BaseTzInfo) -> int:
    """Convert a (hour, minute) in the given timezone to a UTC Unix timestamp.
    If that time has already passed today in the user's timezone, use tomorrow."""
    now = datetime.now(tz)
    candidate = tz.localize(datetime(now.year, now.month, now.day, hour, minute, 0))
    if candidate < now:
        candidate += timedelta(days=1)
    return int(candidate.timestamp())
