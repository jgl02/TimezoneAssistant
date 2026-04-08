import re
from datetime import datetime, timedelta, date
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

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

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
# Date prefix: "4/10", "10/4", "tomorrow", "today", "monday", etc.
# Captured as a named group before the time
_DATE_PREFIX = re.compile(
    r"\b(?:(tomorrow|today|" + "|".join(DAYS) + r")|(\d{1,2})[/\-](\d{1,2}))"
    r"(?:\s+at)?\s+",
    re.IGNORECASE,
)


def _resolve_tz(abbr: str | None) -> pytz.BaseTzInfo | None:
    if not abbr:
        return None
    return pytz.timezone(TZ_ABBREVIATIONS[abbr.upper()]) if abbr.upper() in TZ_ABBREVIATIONS else None


def _resolve_date(prefix_match, ref_date: date) -> date | None:
    """Given a _DATE_PREFIX match and today's date, return the target date."""
    if prefix_match is None:
        return None
    word = prefix_match.group(1)
    m = prefix_match.group(2)
    d = prefix_match.group(3)
    if word:
        word = word.lower()
        if word == "today":
            return ref_date
        if word == "tomorrow":
            return ref_date + timedelta(days=1)
        # Day name: find next occurrence
        target_weekday = DAYS.index(word)
        days_ahead = (target_weekday - ref_date.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7  # "Monday" when today is Monday → next Monday
        return ref_date + timedelta(days=days_ahead)
    if m and d:
        # Assume M/D format (US style); use current year, next year if past
        try:
            candidate = date(ref_date.year, int(m), int(d))
            if candidate < ref_date:
                candidate = date(ref_date.year + 1, int(m), int(d))
            return candidate
        except ValueError:
            return None
    return None


def find_times(content: str, ref_tz: pytz.BaseTzInfo | None = None) -> list[tuple[int, int, date | None, pytz.BaseTzInfo | None]]:
    """Return a list of (hour24, minute, target_date_or_None, inline_tz_or_None).
    target_date is None when no date context was found (caller defaults to today/tomorrow logic).
    ref_tz is the sender's timezone, used to determine 'today' for date resolution."""
    ref_date = datetime.now(ref_tz).date() if ref_tz else datetime.utcnow().date()
    results = []
    seen = set()

    def check_date_prefix(match_start: int) -> date | None:
        # Look for a date keyword/pattern immediately before this time match
        prefix_text = content[:match_start]
        pm = _DATE_PREFIX.search(prefix_text)
        if pm and pm.end() == match_start:
            return _resolve_date(pm, ref_date)
        return None

    for m in _12HR.finditer(content):
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        meridiem = m.group(3).lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        inline_tz = _resolve_tz(m.group(4))
        target_date = check_date_prefix(m.start())
        key = (hour, minute)
        if key not in seen:
            seen.add(key)
            results.append((hour, minute, target_date, inline_tz))

    if not results:
        for m in _24HR.finditer(content):
            hour = int(m.group(1))
            minute = int(m.group(2))
            inline_tz = _resolve_tz(m.group(3))
            target_date = check_date_prefix(m.start())
            key = (hour, minute)
            if key not in seen:
                seen.add(key)
                results.append((hour, minute, target_date, inline_tz))

    return results


def to_unix_timestamp(hour: int, minute: int, tz: pytz.BaseTzInfo, target_date: date | None = None) -> int:
    """Convert a (hour, minute) in the given timezone to a UTC Unix timestamp.
    Uses target_date if provided, otherwise defaults to today — or tomorrow if the time has passed."""
    now = datetime.now(tz)
    if target_date:
        candidate = tz.localize(datetime(target_date.year, target_date.month, target_date.day, hour, minute, 0))
    else:
        candidate = tz.localize(datetime(now.year, now.month, now.day, hour, minute, 0))
        if candidate < now:
            candidate += timedelta(days=1)
    return int(candidate.timestamp())
