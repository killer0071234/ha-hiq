from datetime import timedelta
from typing import List

from ...constants import APP_VERSION


class SystemStatusService:
    def __init__(
        self,
        config,
        plc_info_service,
        push_activity_service,
        scgi_activity_service,
        plc_activity_service,
        udp_activity_service,
        data_logger_activity_service,
        plc_status_service,
        proxy_activity_service,
    ):
        self._config = config
        self._plc_info_service = plc_info_service
        self._push_activity_service = push_activity_service
        self._scgi_activity_service = scgi_activity_service
        self._plc_activity_service = plc_activity_service
        self._udp_activity_service = udp_activity_service
        self._data_logger_activity_service = data_logger_activity_service
        self._app_version = APP_VERSION
        self._plc_status_service = plc_status_service
        self._proxy_activity_service = proxy_activity_service

    @property
    def scgi_port_status(self) -> str:
        # This exists because API had this call in previous version
        return "active"

    @property
    def scgi_request_count(self) -> int:
        return self._scgi_activity_service.requests_received_count

    @property
    def scgi_request_pending_count(self) -> int:
        return self._scgi_activity_service.pending_requests_count

    @property
    def server_version(self) -> str:
        return self._app_version

    @property
    def server_uptime(self) -> timedelta:
        return self._scgi_activity_service.server_uptime

    @property
    def cache_valid_period(self) -> timedelta:
        return self._config.cache_config.valid_period

    @property
    def cache_request_period(self) -> timedelta:
        return self._config.cache_config.request_period

    @property
    def is_push_port_active(self) -> bool:
        return self._config.push_config.enabled

    @property
    def push_plcs_count(self) -> int:
        return len(list(self._plc_info_service.get_push_plc_infos()))

    @property
    def failed_push_acknowledgments_count(self) -> int:
        return self._push_activity_service.failed_push_acknowledgments_count

    @property
    def successful_push_acknowledgments_count(self) -> int:
        return self._push_activity_service.successful_push_acknowledgments_count

    async def get_plcs(self) -> List[int]:
        return [plc_info.nad for plc_info in self._plc_info_service.get_plc_infos()]

    @property
    def push_plc_info_table(self):
        result = []
        for plc_info in self._plc_info_service.get_push_plc_infos():
            nad = plc_info.nad

            plc_status_service = self._plc_status_service[nad]
            # plc_activity = plc_status_service.plc_activity
            plc_info = plc_status_service.plc_info

            status = plc_status_service.plc_status
            alc = plc_status_service.has_alc
            program = plc_info.program_datetime
            downloaded = "N/A"
            response = plc_status_service.response_time
            last_update_time = plc_info.last_update_time

            row = (
                plc_info.created.strftime("%d-%m-%y %H:%M:%S"),
                nad,
                f"{plc_info.ip}:{plc_info.port}",
                status,
                program,
                alc,
                downloaded,
                response,
                last_update_time,
            )
            result.append(row)

        return result

    @property
    def udp_rx_count(self) -> int:
        return self._udp_activity_service.rx_count

    @property
    def udp_tx_count(self) -> int:
        return self._udp_activity_service.tx_count

    @property
    def plc_info_table(self):
        result = []
        for plc_info in self._plc_info_service.get_plc_infos():
            nad = plc_info.nad
            plc_activity = self._plc_activity_service[nad]
            initiated_exchanges_count = plc_activity.initiated_exchanges_count
            failed_exchanges_count = plc_activity.failed_exchanges_count
            last_failed_exchange_time = plc_activity.last_failed_exchange_time
            ip = plc_info.ip
            port = plc_info.port
            origin = plc_info.origin

            row = (
                nad,
                initiated_exchanges_count,
                failed_exchanges_count,
                None
                if last_failed_exchange_time is None
                else last_failed_exchange_time.strftime("%d-%m-%y %H:%M:%S"),
                ip,
                port,
                origin.value,
            )
            result.append(row)

        return result

    @property
    def data_logger_status(self):
        return (
            "active"
            if self._config.data_logger_config.datalogger_enabled
            else "stopped"
        )

    @property
    def data_logger_list(self):
        measurement_tasks = self._data_logger_activity_service.measurement_tasks
        alarm_tasks = self._data_logger_activity_service.alarm_tasks

        return [
            ["sample", *self._tasks_to_row_data(measurement_tasks)],
            ["alarm", *self._tasks_to_row_data(alarm_tasks)],
        ]

    def _tasks_to_row_data(self, tasks):
        tag_count = 0
        trigger_count = 0
        valid_result_count = 0
        invalid_result_count = 0
        last_trigger_datetime = None
        duration = timedelta(milliseconds=0)

        for task in tasks:
            task_activity = self._data_logger_activity_service[task.id]
            trigger_count += task_activity.trigger_count
            tag_count += len(task.targets)
            valid_result_count += task_activity.valid_results
            invalid_result_count += task_activity.invalid_results
            if (
                last_trigger_datetime is None
                or last_trigger_datetime < task_activity.last_trigger_datetime
            ):
                last_trigger_datetime = task_activity.last_trigger_datetime
            if task_activity.duration is not None:
                duration += task_activity.duration

        return (
            tag_count,
            len(tasks),
            trigger_count,
            valid_result_count,
            invalid_result_count,
            last_trigger_datetime.strftime("%d-%m-%y %H:%M:%S")
            if last_trigger_datetime is not None
            else "",
            f"{duration.total_seconds() * 1000:.2f}ms" if duration is not None else "",
        )

    @property
    def proxy_activity_table(self):
        result = []

        for (
            session_id,
            proxy_activity,
        ) in self._proxy_activity_service.extract_proxy_activities():
            last_msg = proxy_activity.last_msg
            last_plc_nad = proxy_activity.last_plc_nad
            msg_count_rx = proxy_activity.msg_count_rx
            msg_count_tx = proxy_activity.msg_count_rx

            row = (session_id, last_msg, last_plc_nad, msg_count_rx, msg_count_tx)
            result.append(row)

        return result
