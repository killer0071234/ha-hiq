import re
from datetime import timedelta
from xml.etree import ElementTree

from ..data_logger_config.data_logger_config import AlarmPriority
from ..data_logger_config.data_logger_config import AlarmRange
from ..data_logger_config.data_logger_config import AlarmTask
from ..data_logger_config.data_logger_config import DataLoggerConfig
from ..data_logger_config.data_logger_config import MeasurementTask
from ..data_logger_config.data_logger_config import Target
from ..data_logger_config.data_logger_config import TaskType
from ..errors import DataLoggerXmlParserError
from ..errors import MissingTagError
from ..errors import UnexpectedTagError


def parse_data_logger_xml(text):
    root = ElementTree.fromstring(text)

    groups = {}
    measurement_tasks = []
    alarm_tasks = []

    for element in root:
        tag = element.tag

        if tag == "list":
            groups = {**groups, **_parse_groups(element)}
        elif tag == "sample":
            measurement_tasks += _parse_measurement_tasks(element)
        elif tag == "alarm":
            alarm_tasks += _parse_alarm_tasks(element)
        elif tag == "event":
            alarm_tasks += _parse_alarm_tasks(element)
        else:
            raise UnexpectedTagError(tag)

    return DataLoggerConfig(groups, measurement_tasks, alarm_tasks)


def _parse_groups(list_element):
    result = {}

    for element in list_element:
        tag = element.tag
        if tag != "group":
            raise UnexpectedTagError(tag)
        name, nads = _parse_group(element)
        result[name] = nads

    return result


def _parse_group(group_element):
    name = None
    nads = []

    for element in group_element:
        tag = element.tag
        if tag == "name":
            name = element.text
        elif tag == "item":
            nads.append(_parse_plc_name(element.text))

    if name is None:
        raise MissingTagError("name")

    return name, nads


def _parse_plc_name(name):
    match = re.search("^c(\\d+)$", name)

    if match is None:
        raise DataLoggerXmlParserError(f"Invalid plc name {name}")

    return int(match[1])


def _parse_measurement_tasks(sample_element):
    result = []

    for element in sample_element:
        tag = element.tag
        if tag != "task":
            raise UnexpectedTagError(tag)
        result.append(_parse_measurement_task(element))

    return result


def _parse_measurement_task(task_element):
    period = None
    targets = []
    enabled = True

    for element in task_element:
        tag = element.tag
        if tag == "period":
            period = _parse_period(element.text)
        elif tag == "variable":
            targets.append(_parse_target(element.text))
        elif tag == "enabled":
            enabled = _parse_enabled(element.text)
        else:
            raise UnexpectedTagError(tag)

    if period is None:
        raise MissingTagError("period")

    return MeasurementTask(period, targets, enabled)


def _parse_period(period):
    match = re.search("^(\\d+)(\\w+)$", period)

    if match is None:
        raise DataLoggerXmlParserError(f"Invalid period {period}")

    value = int(match[1])
    unit = match[2]

    if unit == "h":
        return timedelta(hours=value)
    elif unit == "m":
        return timedelta(minutes=value)
    elif unit == "s":
        return timedelta(seconds=value)
    else:
        raise DataLoggerXmlParserError(f"Invalid period {period}")


def _parse_target(target_text):
    match = re.search(r"^c(\d+)\.(\w+(?:\[\d+\])?)$", target_text)

    if match is not None:
        nad = int(match[1])
        variable = match[2]
        return Target(nad, variable)

    match = re.search(r"^{(\w+)}\.(\w+(?:\[\d+\])?)$", target_text)

    if match is not None:
        group = match[1]
        variable = match[2]
        return Target(group, variable)

    raise DataLoggerXmlParserError(f"Invalid variable {target_text}")


def _parse_enabled(enabled):
    if enabled == "true":
        return True
    elif enabled == "false":
        return False
    else:
        raise DataLoggerXmlParserError(f"Invalid enabled value {enabled}")


def _parse_alarm_tasks(alarm_element):
    result = []

    for element in alarm_element:
        tag = element.tag
        if tag != "task":
            raise UnexpectedTagError(tag)
        result.append(_parse_alarm_task(element, alarm_element.tag))

    return result


def _parse_alarm_task(task_element, type):
    period = None
    targets = []
    enabled = True
    alarm_class = ""
    priority = AlarmPriority.MEDIUM
    message = ""
    low_limit = None
    high_limit = None
    hysteresis = None
    alarm_range = None
    task_type = TaskType.ALARM if type == "alarm" else TaskType.EVENT

    for element in task_element:
        tag = element.tag
        if tag == "period":
            period = _parse_period(element.text)
        elif tag == "variable":
            targets.append(_parse_target(element.text))
        elif tag == "enabled":
            enabled = _parse_enabled(element.text)
        elif tag == "class":
            alarm_class = element.text
        elif tag == "priority":
            priority = _parse_alarm_priority(element.text)
        elif tag == "message":
            message = element.text
        elif tag == "lolimit":
            low_limit = _parse_float(element.text)
        elif tag == "hilimit":
            high_limit = _parse_float(element.text)
        elif tag == "hysteresis":
            hysteresis = _parse_float(element.text)
        else:
            raise UnexpectedTagError(tag)

    if period is None:
        raise MissingTagError("period")

    if low_limit is not None or high_limit is not None:
        alarm_range = AlarmRange(
            float("-inf") if low_limit is None else low_limit,
            float("+inf") if high_limit is None else high_limit,
            0 if hysteresis is None else hysteresis,
        )

    return AlarmTask(
        period, targets, enabled, alarm_class, priority, alarm_range, message, task_type
    )


def _parse_float(value):
    try:
        return float(value)
    except ValueError:
        raise DataLoggerXmlParserError(f"Invalid number {value}")


def _parse_alarm_priority(alarm_priority):
    try:
        return AlarmPriority[alarm_priority.upper()]
    except KeyError:
        raise DataLoggerXmlParserError(f"Invalid alarm priority {alarm_priority}")
