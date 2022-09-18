import asyncio

from ....services.rw_service.scgi_communication.r_response import RResponse
from ....services.rw_service.subservices.plc_activity_service.plc_activity import (
    PlcActivity,
)


class PlcStatusServiceFacade:
    """
    Public interface for `PlcStatusService`
    """

    def __init__(self, plc_status_service):
        self._plc_status_service_manager = plc_status_service

    async def process(self, nad, requests):
        coroutines = (self._process_request(nad, request) for request in requests)
        responses = await asyncio.gather(*coroutines)
        return list(responses)

    async def _process_request(self, nad, request):
        try:
            (value, description) = await self._get_value(nad, request.tag_name)
            return RResponse.create(request.name, request.tag_name, value, description)
        except KeyError:
            return RResponse.create(
                request.name, request.tag_name, code=RResponse.Code.UNKNOWN
            )

    async def _get_value(self, nad, tag_name):
        plc_status_service = self._plc_status_service_manager[nad]
        return await SinglePlcStatusServiceFacade(plc_status_service).get(tag_name)


class SinglePlcStatusServiceFacade:
    def __init__(self, single_plc_status_service):
        self._single_plc_status_service = single_plc_status_service

        self._actions = {
            "timestamp": (self._timestamp, "Program download timestamp."),
            "ip_port": (self._ip_port, "IP address and UDP port of the controller."),
            "response_time": (
                self._response_time,
                "Last communication cycle duration in milliseconds.",
            ),
            "plc_program_status": (self._plc_program_status, "Program status."),
            "alc_file_status": (self._alc_file_status, "Allocation file status."),
            # "plc_status": (
            #     self._plc_status,
            #     "Controller status."
            # ),
            "bytes_transferred": (
                self._bytes_transferred,
                "Total number of bytes sent to and received from controller.",
            ),
            "alc_file": (
                self._alc_file,
                "Complete allocation file for the controller, in ASCII format.",
            ),
            "comm_error_count": (
                self._comm_error_count,
                "Total number of communication errors for controller.",
            ),
        }

    async def get(self, tag_name):
        action, description = self._actions[tag_name]
        value = await action()
        return value, description

    async def _timestamp(self):
        return str(self._single_plc_status_service.timestamp)

    async def _ip_port(self):
        ip_port = self._single_plc_status_service.ip_port
        if ip_port is not None:
            ip, port = ip_port
            if ip is not None:
                return f"{ip}:{port}"
        return "?"

    async def _response_time(self):
        response_time = self._single_plc_status_service.response_time
        return (
            "?"
            if response_time is None
            else f"{int(response_time.total_seconds() * 1000)}"
        )

    async def _plc_program_status(self):
        device_status = self._single_plc_status_service.device_status

        if device_status == PlcActivity.DeviceStatus.UNKNOWN:
            return "?"
        elif device_status == PlcActivity.DeviceStatus.OFFLINE:
            return "-"
        elif device_status == PlcActivity.DeviceStatus.NO_PROGRAM:
            return "missing"
        elif device_status == PlcActivity.DeviceStatus.OK:
            return "ok"

    async def _alc_file_status(self):
        if (
            self._single_plc_status_service.device_status
            == PlcActivity.DeviceStatus.OFFLINE
        ):
            return "-"
        return "ok" if self._single_plc_status_service.has_alc else "missing"

    async def _plc_status(self):
        status = self._single_plc_status_service.plc_status
        return "?" if status is None else str(status.name)

    async def _bytes_transferred(self):
        return str(self._single_plc_status_service.bytes_transferred)

    async def _alc_file(self):
        alc_file = await self._single_plc_status_service.get_alc_text()
        return "" if alc_file is None else f"\n{alc_file}\n"

    async def _comm_error_count(self):
        return str(self._single_plc_status_service.communication_error_count)
