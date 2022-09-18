from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from typing import Union


@dataclass
class Entity:
    id: Optional[int]


@dataclass
class Measurement(Entity):
    nad: int
    tag: str
    value: str
    timestamp: datetime


@dataclass
class Alarm(Entity):
    nad: int
    tag: str
    priority: int
    value: str
    alarm_type: int
    alarm_class: str
    message: str
    timestamp_raise: datetime
    timestamp_gone: Optional[datetime] = None
    timestamp_ack: Optional[datetime] = None

    @classmethod
    def create_from_db_result(
        cls,
        alarm_id: int,
        nad: int,
        tag: str,
        priority: int,
        value: str,
        alarm_type: int,
        alarm_class: str,
        message: str,
        timestamp_raise: datetime,
        timestamp_gone: Union[datetime, str],
        timestamp_ack: Union[datetime, str],
    ):
        timestamp_gone = None if isinstance(timestamp_gone, str) else timestamp_gone
        timestamp_ack = None if isinstance(timestamp_ack, str) else timestamp_ack

        return Alarm(
            alarm_id,
            nad,
            tag,
            priority,
            value,
            alarm_type,
            alarm_class,
            message,
            timestamp_raise,
            timestamp_gone,
            timestamp_ack,
        )

    def __str__(self):
        return (
            f"c{self.nad} {self.tag}={self.value}"
            f" {self.alarm_type} {self.alarm_class} {self.message}"
        )

    @property
    def is_timestamp_gone_default(self):
        return self.timestamp_gone is None

    @property
    def is_timestamp_ack_default(self):
        return self.timestamp_ack is None


@dataclass
class Relay(Entity):
    user_id: int
    enabled: int
    session_id: int
    message_count_rx: int
    message_count_tx: int
    last_message: datetime
    last_controller_nad: int
