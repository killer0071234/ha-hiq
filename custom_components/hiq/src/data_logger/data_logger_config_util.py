from itertools import chain

from ..config.data_logger_config.data_logger_config import AlarmRange
from .task import DataLoggerAlarmTask
from .task import DataLoggerMeasurementTask


def _extract_tasks(config):
    measurements = _extract_measurement_tasks(config)
    alarms = _extract_alarm_tasks(config, len(measurements))
    return measurements, alarms


def _extract_measurement_tasks(config):
    return [
        _create_measurement_task(i, task, config.groups)
        for i, task in enumerate(config.measurement_tasks)
        if task.enabled
    ]


def _create_measurement_task(task_id, task, groups):
    expanded_targets = _expand_targets(task.targets, groups)
    return DataLoggerMeasurementTask(task_id, task.period, list(expanded_targets))


def _extract_alarm_tasks(config, first_id: int):
    return [
        _create_alarm_task(first_id + i, task, config.groups)
        for (i, task) in enumerate(config.alarm_tasks)
        if task.enabled
    ]


def _create_alarm_task(task_id, task, groups):
    expanded_targets = _expand_targets(task.targets, groups)

    return DataLoggerAlarmTask(
        task_id,
        task.period,
        list(expanded_targets),
        task.alarm_class,
        task.priority,
        AlarmRange() if task.range is None else task.range,
        task.message,
        task.type,
    )


def _expand_targets(targets, groups):
    return chain(*(_expand_target(target, groups) for target in targets))


def _expand_target(target, groups):
    if target.is_group:
        group_name = target.context
        try:
            for nad in groups[group_name]:
                (yield nad, target.variable)
        except KeyError:
            return
    else:
        (yield target.context, target.variable)
