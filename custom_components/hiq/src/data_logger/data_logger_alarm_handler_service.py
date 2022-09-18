import asyncio
from datetime import datetime

from ..input_output.db.model import Alarm
from .errors import UnexpectedValue


class DataLoggerAlarmHandlerService:
    def __init__(self, log, repository):
        self._log = log
        self._repository = repository

    async def on_new_data(
        self, measurements, message, alarm_class, priority, alarm_range, task_type
    ):
        self._log.debug(lambda: f"Alarm - {len(measurements)} variables")

        not_acknowledged = await self._get_not_acknowledged_alarms(
            [(m.nad, m.variable) for m in measurements]
        )

        to_create_alarms = []
        to_clear_alarm_ids = []

        for measurement in measurements:
            try:
                not_acknowledged_alarms = not_acknowledged[measurement.nad][
                    measurement.variable
                ]
            except KeyError:
                not_acknowledged_alarms = []

            not_cleared_alarm_ids = [
                alarm.id
                for alarm in not_acknowledged_alarms
                if alarm.is_timestamp_gone_default
            ]

            (_is_in_range, _is_in_range_with_hysteresis) = self._is_in_range(
                measurement.value, alarm_range
            )

            if _is_in_range_with_hysteresis:
                to_clear_alarm_ids = not_cleared_alarm_ids
            elif not _is_in_range and len(not_cleared_alarm_ids) == 0:
                to_create_alarms.append(
                    Alarm(
                        None,
                        measurement.nad,
                        measurement.variable,
                        priority.value,
                        measurement.value,
                        task_type,
                        alarm_class,
                        message,
                        datetime.now(),
                    )
                )

        if len(to_create_alarms) > 0:
            self._log.debug(
                lambda: "Raise: " + ", ".join((str(a) for a in to_create_alarms))
            )

        if len(to_clear_alarm_ids) > 0:
            self._log.debug(
                lambda: "Clear: "
                + ", ".join((str(a_id) for a_id in to_clear_alarm_ids))
            )

        await asyncio.gather(
            self._repository.create_alarms(to_create_alarms),
            self._repository.clear_alarms(to_clear_alarm_ids, datetime.now()),
        )

    async def _get_not_acknowledged_alarms(self, conditions):
        alarms = await self._repository.get_not_acknowledged_alarms(conditions)

        result = {}
        for alarm in alarms:
            try:
                alarms_for_nad = result[alarm.nad]
            except KeyError:
                alarms_for_nad = {}
                result[alarm.nad] = alarms_for_nad

            try:
                alarms_for_tag = alarms_for_nad[alarm.tag]
            except KeyError:
                alarms_for_tag = []
                alarms_for_nad[alarm.tag] = alarms_for_tag

            alarms_for_tag.append(alarm)

        return result

    @classmethod
    def _is_in_range(cls, value_str, alarm_range):
        try:
            value = float(value_str)
        except ValueError:
            raise UnexpectedValue(value_str, "Expected number")

        _is_in_range = alarm_range.low <= value <= alarm_range.high

        low_with_hysteresis = alarm_range.low + alarm_range.hysteresis
        high_with_hysteresis = alarm_range.high - alarm_range.hysteresis

        _is_in_range_with_hysteresis = (
            low_with_hysteresis <= value <= high_with_hysteresis
        )

        return _is_in_range, _is_in_range_with_hysteresis
