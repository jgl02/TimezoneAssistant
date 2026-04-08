import re
from datetime import datetime, date, timedelta
import pytz

# Matches: 2pm, 2 pm, 2:30pm, 2:30 PM, 14:00, 14:30
_12HR = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.IGNORECASE)
_24HR = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")


def find_times(content: str) -> list[tuple[int, int]]:
    """Return a list of (hour24, minute) tuples found in the message."""
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
        key = (hour, minute)
        if key not in seen:
            seen.add(key)
            results.append(key)

    # Only parse 24hr if no 12hr times were found (avoids double-matching "2:30pm")
    if not results:
        for m in _24HR.finditer(content):
            hour = int(m.group(1))
            minute = int(m.group(2))
            key = (hour, minute)
            if key not in seen:
                seen.add(key)
                results.append(key)

    return results


def to_unix_timestamp(hour: int, minute: int, tz: pytz.BaseTzInfo) -> int:
    """Convert a (hour, minute) in the given timezone to a UTC Unix timestamp.
    If that time has already passed today in the user's timezone, use tomorrow."""
    now = datetime.now(tz)
    candidate = tz.localize(datetime(now.year, now.month, now.day, hour, minute, 0))
    if candidate < now:
        candidate += timedelta(days=1)
    return int(candidate.timestamp())
