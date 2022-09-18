import asyncio
from datetime import timedelta
from timeit import default_timer
from typing import List

from ...constants import DATA_LOGGER_ALARMS_TABLE
from ...constants import DATA_LOGGER_SAMPLES_TABLE
from ...constants import RELAYS_TABLE
from .model import Alarm
from .query_builder import QueryBuilder


class Repository:
    _NAD_SIZE = 5
    _TIME_ISO_FORMAT_MAX_SIZE = 26
    _TAG_MAX_SIZE = 40
    _VALUE_MAX_SIZE = 16
    _ALARM_MAX_TYPE_SIZE = 11
    _ALARM_MAX_MESSAGE_SIZE = 50
    _ALARM_MAX_CLASS_SIZE = 20

    def __init__(self, log, db, config, cpu_intensive_task_runner):
        self._log = log
        self._db = db
        self._db_config = config.dbase_config
        self._query_builder = QueryBuilder(self._db_config.max_query_size)
        self._cpu_intensive_task_runner = cpu_intensive_task_runner

        self._measurements = DATA_LOGGER_SAMPLES_TABLE
        self._alarms = DATA_LOGGER_ALARMS_TABLE
        self._relays = RELAYS_TABLE

    async def create_alarms(self, alarms: List[Alarm]):
        t = default_timer()
        self._log.debug("Preparing queries...")

        queries = self._query_builder.create_insert_queries(
            self._alarms,
            (
                "nad",
                "tag",
                "priority",
                "value",
                "type",
                "class",
                "message",
                "timestamp_raise",
                "timestamp_gone",
                "timestamp_ack",
            ),
            [
                (
                    str(alarm.nad),
                    str(alarm.tag),
                    str(alarm.priority),
                    str(alarm.value),
                    str(alarm.alarm_type.value),
                    str(alarm.alarm_class),
                    str(alarm.message),
                    str(alarm.timestamp_raise.isoformat(sep=" ", timespec="seconds")),
                    "0000-00-00"
                    if alarm.timestamp_gone is None
                    else alarm.timestamp_gone.isoformat(sep=" ", timespec="seconds"),
                    "0000-00-00"
                    if alarm.timestamp_ack is None
                    else alarm.timestamp_ack.isoformat(sep=" ", timespec="seconds"),
                )
                for alarm in alarms
            ],
            [
                self._NAD_SIZE,
                self._TAG_MAX_SIZE,
                self._VALUE_MAX_SIZE,
                self._ALARM_MAX_TYPE_SIZE,
                self._ALARM_MAX_CLASS_SIZE,
                self._ALARM_MAX_MESSAGE_SIZE,
                self._TIME_ISO_FORMAT_MAX_SIZE,
            ],
        )

        self._log.debug(
            lambda: f"Prepared {len(queries)} queries in {timedelta(seconds=default_timer() - t)}"
        )

        for query in queries:
            asyncio.get_running_loop().create_task(self._db.execute_query(query))

    async def clear_alarms(self, alarm_ids, timestamp):
        if len(alarm_ids) == 0:
            return

        conditions = [f"id={alarm_id}" for alarm_id in alarm_ids]

        predicate = " OR ".join(conditions)
        timestamp_gone = timestamp.isoformat(sep=" ", timespec="seconds")
        query = f"UPDATE {self._alarms} SET timestamp_gone = '{timestamp_gone}' WHERE {predicate}"

        asyncio.get_running_loop().create_task(self._db.execute_query(query))

    async def get_not_acknowledged_alarms(self, conditions):
        query = f"SELECT id, nad, tag, value, type, class, message, timestamp_raise, timestamp_gone, timestamp_ack FROM {self._alarms}"

        if len(conditions) > 0:
            predicate = (
                f"(nad = {nad} AND tag = '{tag}' AND timestamp_ack = '0000-00-00')"
                for nad, tag in conditions
            )
            predicate_joined = " OR ".join(pred for pred in predicate)

            query = f"SELECT id, nad, tag, priority, value, type, class, message, timestamp_raise, timestamp_gone, timestamp_ack FROM {self._alarms} WHERE {predicate_joined}"

        result = await self._db.execute_query(query)

        return [Alarm.create_from_db_result(*values) for values in result]

    async def create_measurements(self, measurements):
        t = default_timer()
        self._log.debug("Preparing queries...")

        queries = self._query_builder.create_insert_queries(
            self._measurements,
            ("nad", "tag", "value", "timestamp"),
            [
                (
                    str(m.nad),
                    str(m.tag),
                    str(m.value),
                    str(m.timestamp.isoformat(sep=" ", timespec="seconds")),
                )
                for m in measurements
            ],
            [
                self._NAD_SIZE,
                self._TAG_MAX_SIZE,
                self._VALUE_MAX_SIZE,
                self._TIME_ISO_FORMAT_MAX_SIZE,
            ],
        )

        self._log.debug(
            lambda: f"Prepared {len(queries)} queries in {timedelta(seconds=default_timer() - t)}"
        )

        for query in queries:
            asyncio.get_running_loop().create_task(self._db.execute_query(query))

    @classmethod
    def _reduce_to_disjunction(cls, accumulator, condition):
        return condition if accumulator is None else accumulator | condition

    async def get_relays(self):

        query = (
            f"SELECT user_id, enabled, session_id, message_count_rx, message_count_tx, last_message, "
            f"last_controller_nad FROM {self._relays}"
        )

        result = await self._db.execute_query(query)
        return result

    async def exist_in_relays_table(self, nad):
        query = f"SELECT user_id, enabled, session_id, message_count_rx, message_count_tx, last_message, last_controller_nad FROM {self._relays} WHERE session_id = {nad} AND enabled != 0"

        result = await self._db.execute_query(query)
        return len(result) != 0

    async def update_relays(self, session_id, plc_proxy_activity):
        query = f"UPDATE {self._relays} SET message_count_tx = {plc_proxy_activity.msg_count_tx}, message_count_rx = {plc_proxy_activity.msg_count_rx}, last_message = {plc_proxy_activity.last_msg} WHERE session_id = {session_id}"

        await self._db.execute_query(query)

    async def get_enabled_with_session_id_in(self, session_id_list):
        if len(session_id_list) == 0:
            return []
        query = f"SELECT session_id FROM {self._relays} WHERE session_id IS IN {session_id_list} AND enabled!= 0"

        rows = await self._db.execute_query(query)

        return [row[0] for row in rows]
