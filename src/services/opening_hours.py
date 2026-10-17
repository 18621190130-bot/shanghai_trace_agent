"""Conservative today-only time intervals. Weekly prose is never guessed."""
from datetime import datetime
import re
from ..world_models import OpenStatus, SHANGHAI


def shanghai_time(value=None):
    if value is None:return datetime.now(SHANGHAI)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Opening evaluation requires a timezone-aware datetime')
    return value.astimezone(SHANGHAI)


def parse_opening_intervals(opentime_today):
    """The existing strict grammar, shared by present-time and ETA evaluation."""
    if not isinstance(opentime_today, str) or not opentime_today.strip():return None
    intervals = []
    for token in re.split('[;；,，]', opentime_today.strip()):
        match = re.fullmatch(r'\s*(\d{1,2}):(\d{2})\s*[-–—~至]\s*(\d{1,2}):(\d{2})\s*', token)
        if not match:return None
        h1, m1, h2, m2 = map(int, match.groups())
        if h1 > 23 or m1 > 59 or h2 > 24 or m2 > 59 or (h2 == 24 and m2 != 0):return None
        start, end = h1*60+m1, h2*60+m2
        if start == end:return None
        intervals.append((start, end))
    return intervals


def resolve_open_status(opentime_today, current_local_time=None):
    current = shanghai_time(current_local_time)
    intervals = parse_opening_intervals(opentime_today)
    if intervals is None:return OpenStatus.UNKNOWN
    now = current.hour*60+current.minute+current.second/60
    if any((start <= now < end if start < end else now >= start or now < end) for start, end in intervals):
        return OpenStatus.OPEN
    return OpenStatus.CLOSED
