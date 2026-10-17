"""Small ETA extension of the frozen strict today-hours parser."""
from datetime import datetime, timedelta
from ..weather_models import SHANGHAI, local_time
from ..world_models import OpenStatus
from .opening_hours import parse_opening_intervals, resolve_open_status


class OpeningHoursEvaluator:
    def evaluate_open_status(self, opening_hours, at_time, *, fetched_at):
        at_time = local_time(at_time)
        try:
            fetched = datetime.fromisoformat(fetched_at)
            fetched = local_time(fetched)
        except (ValueError, TypeError):
            return OpenStatus.UNKNOWN
        if fetched.date() != at_time.date():
            return OpenStatus.UNKNOWN
        return resolve_open_status(opening_hours, at_time)

    def closes_at(self, opening_hours, at_time, *, fetched_at):
        at_time = local_time(at_time)
        if self.evaluate_open_status(opening_hours, at_time, fetched_at=fetched_at) != OpenStatus.OPEN:
            return None
        intervals = parse_opening_intervals(opening_hours)
        midnight = datetime.combine(at_time.date(), datetime.min.time(), tzinfo=SHANGHAI)
        windows = []
        for start, end in intervals:
            begin = midnight + timedelta(minutes=start)
            finish = midnight + timedelta(minutes=end + (1440 if end < start else 0))
            windows.append((begin, finish))
            if end < start:
                windows.append((begin - timedelta(days=1), finish - timedelta(days=1)))
        # Adjacent/overlapping intervals form one continuously open window.
        merged = []
        for begin, finish in sorted(windows):
            if merged and begin <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(finish, merged[-1][1]))
            else:
                merged.append((begin, finish))
        return next((finish for begin, finish in merged if begin <= at_time < finish), None)
