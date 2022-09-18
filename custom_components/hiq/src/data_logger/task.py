from dataclasses import dataclass
from datetime import timedelta
from typing import List
from typing import Optional
from typing import Tuple

from ..config.data_logger_config.data_logger_config import AlarmPriority
from ..config.data_logger_config.data_logger_config import AlarmRange
from ..general.util import humanize_timedelta


@dataclass
class DataLoggerTask:
    id: int
    period: timedelta
    # list of (nad, variable name) pairs
    targets: List[Tuple[int, str, Optional[int]]]

    @property
    def _targets_str(self):
        def format_index(i):
            return f"[{i}]" if i is not None else ""

        return ", ".join(
            (f"c{nad}.{var}{format_index(idx)}" for (nad, var, idx) in self.targets)
        )

    @property
    def _period_str(self):
        return humanize_timedelta(self.period)


@dataclass
class DataLoggerMeasurementTask(DataLoggerTask):
    def __str__(self):
        return f"{self._period_str}: {self._targets_str}"


@dataclass
class DataLoggerAlarmTask(DataLoggerTask):
    alarm_class: str
    priority: AlarmPriority
    range: AlarmRange
    message: str
    type: int

    def __str__(self):
        return (
            f"{self._period_str}, {self.alarm_class}, "
            f'{self.priority.name}, {self.range}, "{self.message}": {self._targets_str}'
        )
