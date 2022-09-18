"""
Each task has associated `execution period`.

From `execution period` `scheduling range` is determined by the following rules:
- if execution period is less than one minute, `scheduling range` is one minute.
- else if execution period is less than one hour, `scheduling range` is one hour.
- else if scheduling range is one day.

Task scheduling will be done periodically each passed `execution period` counting from last full
`scheduling range` (minute, hour or day) until `scheduling range` has passed - then countdown is
reset and everything is repeated.

Example: If `execution period` is 17s, task should be executed on following seconds withing each
minute: 0, 17, 24, 41, 58. These moments will be called `execution points`.
"""
from datetime import timedelta
from enum import auto
from enum import Enum

_MINUTE = timedelta(minutes=1)
_HOUR = timedelta(hours=1)
_DAY = timedelta(days=1)


class SchedulingRange(Enum):
    MINUTE = auto()
    HOUR = auto()
    DAY = auto()


_scheduling_range_timedeltas = {
    SchedulingRange.MINUTE: _MINUTE,
    SchedulingRange.HOUR: _HOUR,
    SchedulingRange.DAY: _DAY,
}


def calculate_wait_time(period, now):
    """
    Calculate time until next `execution point`.
    """

    scheduling_range = _calculate_scheduling_range(period)
    period_s = period.seconds
    scheduling_range_s = _scheduling_range_timedeltas[scheduling_range].seconds
    current_s = _calculate_elapsed_time_in_scheduling_range(
        now, scheduling_range
    ).seconds
    time_until_scheduling_range_end_s = scheduling_range_s - current_s
    time_until_period_end_s = period_s - current_s % period_s
    result_s = min(time_until_scheduling_range_end_s, time_until_period_end_s)
    return timedelta(seconds=result_s)


def _calculate_elapsed_time_in_scheduling_range(time, scheduling_range):
    """
    Calculate how much time has passed since the last full `scheduling range`.
    """

    if scheduling_range == SchedulingRange.MINUTE:
        return timedelta(seconds=time.second)
    elif scheduling_range == SchedulingRange.HOUR:
        return timedelta(minutes=time.minute, seconds=time.second)
    else:
        return timedelta(hours=time.hour, minutes=time.minute, seconds=time.second)


def _calculate_scheduling_range(period):
    if period <= _MINUTE:
        return SchedulingRange.MINUTE
    elif period <= _HOUR:
        return SchedulingRange.HOUR
    else:
        return SchedulingRange.DAY
