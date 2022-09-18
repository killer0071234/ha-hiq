from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Dict
from typing import List
from typing import Optional
from typing import Union


@dataclass(frozen=True)
class Target:
    # group name or nad
    context: Union[int, str]
    variable: str

    @property
    def is_group(self):
        return isinstance(self.context, str)


class TaskType(Enum):
    SAMPLE = 0
    ALARM = 1
    EVENT = 2


@dataclass(frozen=True)
class Task:
    period: timedelta
    targets: List[Target]
    enabled: bool


@dataclass(frozen=True)
class MeasurementTask(Task):
    pass


class AlarmPriority(Enum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2


@dataclass(frozen=True)
class AlarmRange:
    low: float = 0
    high: float = 0
    hysteresis: float = 0

    def __str__(self):
        result = f"{self.low} <= x <= {self.high}"
        if self.hysteresis != 0:
            result += f" (+/-{self.hysteresis})"
        return result


@dataclass(frozen=True)
class AlarmTask(Task):
    alarm_class: str
    priority: AlarmPriority
    range: Optional[AlarmRange]
    message: str
    type: TaskType


@dataclass(frozen=True)
class DataLoggerConfig:
    # key is group name, value is list of nads
    groups: Dict[str, List[int]]
    measurement_tasks: List[MeasurementTask]
    alarm_tasks: List[AlarmTask]
