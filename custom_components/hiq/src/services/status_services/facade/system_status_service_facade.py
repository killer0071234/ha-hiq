import asyncio

from ....general.util import humanize_timedelta
from ....general.util import tabulate
from ....services.rw_service.scgi_communication.r_response import RResponse


class SystemStatusServiceFacade:
    """
    Public interface for `SystemStatusService`
    """

    def __init__(self, system_status_service):
        self._system_status_service = system_status_service

        self._actions = {
            "scgi_port_status": (
                self._scgi_port_status,
                "SCGI port status can be 'active' or empty (server is down).",
            ),
            "scgi_request_count": (
                self._scgi_request_count,
                "Total number of executed requests since startup.",
            ),
            "scgi_request_pending": (
                self._scgi_request_pending,
                "Number of requests pending to be processed.",
            ),
            "server_version": (
                self._server_version,
                "Server version, 'major.minor.release'.",
            ),
            "server_uptime": (
                self._server_uptime,
                "Time since the server is started, 'hh:mm:ss' or 'xx days, hh:mm:ss'.",
            ),
            "cache_valid": (
                self._cache_valid,
                "Time in seconds after cached value is invalidated. If value is 0, cache "
                "is disabled.",
            ),
            "cache_request": (
                self._cache_request,
                "Time in seconds after data is read from cache, but communication request "
                "is initiated. If value is 0, no requests are generated until cache expires.",
            ),
            "push_port_status": (
                self._push_port_status,
                "Push port status can be 'active' or 'inactive'.",
            ),
            "push_count": (
                self._push_count,
                "Total number of push messages received from controllers.",
            ),
            "push_list_count": (
                self._push_list_count,
                "Total number of controllers in push list.",
            ),
            "push_ack_errors": (
                self._push_ack_errors,
                "Total number of push acknowledge errors.",
            ),
            "nad_list": (
                self._nad_list,
                "List of available controllers, push and autodetect list combined.",
            ),
            "push_list": (
                self._push_list,
                "Push list represents the list of Cybro controllers that sent push message "
                "to the server, containing last message timestamp, controller NAD, IP "
                "address and port, controller status, program status, allocation status, "
                "last program timestamp, response time in milliseconds and last plc info update time.",
            ),
            "udp_rx_count": (
                self._udp_rx_count,
                "Total number of UDP packets received through UDP proxy.",
            ),
            "udp_tx_count": (
                self._udp_tx_count,
                "Total number of UDP packets transmitted through UDP proxy.",
            ),
            "abus_list": (
                self._abus_list,
                "Abus list contains detailed information for low level communication "
                "between SCGI server and Cybro controllers. It is shown NAD, total number "
                "of abus messages, number of abus errors, last error timestamp, last error "
                "code and bandwidth used for each controller. Bandwidth represents the "
                "amount of time spent for communication in last 60 seconds for particular "
                "controller.",
            ),
            "datalogger_status": (
                self._datalogger_status,
                "Datalogger module can be 'active' or 'stopped'.",
            ),
            "datalogger_list": (
                self._datalogger_list,
                "DataLogger list contains detailed data for datalogger sample, alarm "
                "type of task, number of tags for this type of task, number "
                "of tasks for this type, number of tasks triggering, last trigger "
                "timestamp, number of correctly read tags, number of unknown tags or for "
                "some other reason not read tags, last communication status and complete "
                "task execution time.",
            ),
            "proxy_activity_list": (
                self._proxy_activity_list,
                "Proxy activity list represents data for proxy activity - last_msg"
                "last_plc_nad, msg_count_rx, msg_count_tx",
            ),
        }

    async def process(self, requests):
        coroutines = (self._process_request(request) for request in requests)
        responses = await asyncio.gather(*coroutines)
        return list(responses)

    async def _process_request(self, request):
        try:
            (value, description) = await self.get(request.tag_name)
            return RResponse.create(request.name, request.tag_name, value, description)
        except KeyError:
            return RResponse.create(
                request.name, request.tag_name, code=RResponse.Code.UNKNOWN
            )

    async def get(self, tag_name):
        action, description = self._actions[tag_name]
        value = await action()
        return value, description

    async def _scgi_port_status(self):
        return self._system_status_service.scgi_port_status

    async def _scgi_request_count(self):
        return str(self._system_status_service.scgi_request_count)

    async def _scgi_request_pending(self):
        return str(self._system_status_service.scgi_request_pending_count)

    async def _server_version(self):
        return self._system_status_service.server_version

    async def _server_uptime(self):
        return humanize_timedelta(
            self._system_status_service.server_uptime.total_seconds()
        )

    async def _cache_valid(self):
        return str(self._system_status_service.cache_valid_period.seconds)

    async def _cache_request(self):
        return str(self._system_status_service.cache_request_period.seconds)

    async def _push_port_status(self):
        if self._system_status_service.is_push_port_active:
            return "active"
        else:
            return "inactive"

    async def _push_count(self):
        return str(self._system_status_service.successful_push_acknowledgments_count)

    async def _push_list_count(self):
        return str(self._system_status_service.push_plcs_count)

    async def _push_ack_errors(self):
        return str(self._system_status_service.failed_push_acknowledgments_count)

    async def _nad_list(self):
        return [str(nad) for nad in await self._system_status_service.get_plcs()]

    async def _push_list(self):
        column_width = [10, 10, 20, 15, 20, 15, 20, 20, 35]
        headers = [
            "push",
            "nad",
            "ip:port",
            "status",
            "program",
            "alc",
            "downloaded",
            "response",
            "last_update_time",
        ]

        data = []
        for item in self._system_status_service.push_plc_info_table:
            data += str(item)
        table = tabulate(column_width, headers, data)

        return table

    async def _udp_rx_count(self):
        return str(self._system_status_service.udp_rx_count)

    async def _udp_tx_count(self):
        return str(self._system_status_service.udp_tx_count)

    async def _abus_list(self):
        column_width = [15, 15, 15, 20, 20, 15, 15]
        headers = ["nad", "total", "errors", "last error at", "ip", "port", "origin"]
        data = []
        for row in self._system_status_service.plc_info_table:
            row_str = []
            for item in row:
                row_str.append(str(item))
            data.append(row_str)
        table = tabulate(column_width, headers, data)

        return table

    async def _datalogger_status(self):
        return self._system_status_service.data_logger_status

    async def _datalogger_list(self):
        column_width = [15, 15, 15, 15, 20, 20, 20, 20]
        headers = [
            "type",
            "tags",
            "tasks",
            "trigger count",
            "read tags",
            "unknown tags",
            "last trigger",
            "duration",
        ]
        data = []

        for data_logger_list in self._system_status_service.data_logger_list:
            data_logger_list_str = []
            for item in data_logger_list:
                data_logger_list_str.append(str(item))
            data.append(data_logger_list_str)

        table = tabulate(column_width, headers, data)

        return table

    async def _proxy_activity_list(self):
        column_width = [20, 20, 20, 20, 20]
        data = []
        for item in self._system_status_service.proxy_activity_table:
            data += str(item)
        headers = [
            "session_id",
            "last_msg",
            "last_plc_nad",
            "msg_count_rx",
            "msg_count_tx",
        ]
        table = tabulate(column_width, headers, data)
        return table
