from asyncio import CancelledError

from ......constants import MAX_FRAME_BYTES
from ......constants import RW_NAD
from ......general.errors import ExchangerTimeoutError
from ......general.misc import create_task_callback
from ......general.transaction_id_generator import transaction_id_generator
from ......services.plc_info_service.plc_info import PlcInfo
from ......services.rw_service.subservices.plc_comm_service.plc_client_manager.plc_client.plc_client import (
    PlcClient,
)


class PlcClientManager:
    def __init__(
        self,
        log,
        client_log,
        loop,
        plc_info_service,
        plc_activity_service,
        detection_service,
        config,
        cpu_intensive_task_runner,
    ):
        self._log = log
        self._client_log = client_log
        self._loop = loop
        self._nad = RW_NAD
        self._plc_info_service = plc_info_service
        self._plc_activity_service = plc_activity_service
        self._max_frame_length = MAX_FRAME_BYTES
        self._plc_detection_service = detection_service
        self._config = config
        self._plc_clients_by_nad = {}
        self._cpu_intensive_task_runner = cpu_intensive_task_runner

        self._exchanger = None

    def set_exchanger(self, exchanger):
        self._exchanger = exchanger

    def on_plc_info_set(self, plc_info):
        if plc_info.origin == PlcInfo.Origin.PROXY:
            return

        nad = plc_info.nad

        if plc_info.has_ip:
            self._set(nad, self._create_plc_client(plc_info))
        elif plc_info.origin == PlcInfo.Origin.STATIC:
            self._set(nad, None)
        else:
            self._remove(nad)
            future_plc_client = self._loop.create_future()
            self._plc_clients_by_nad[nad] = future_plc_client

            if self._plc_detection_service is not None:
                self._log.info(f"Set pending plc client c{plc_info.nad}")
                self._loop.create_task(self._autodetect(plc_info)).add_done_callback(
                    create_task_callback(self._log)
                )
            else:
                future_plc_client.cancel()

    def on_plc_info_removed(self, nad):
        self._remove(nad)

    async def get(self, nad):
        try:
            try:
                return await self._plc_clients_by_nad[nad]
            except KeyError:
                plc_info = self._plc_info_service.create(PlcInfo.Origin.AUTO, nad)
                self._plc_info_service.set_plc_info(plc_info)
                return await self._plc_clients_by_nad[nad]
        except CancelledError:
            return None

    def _set(self, nad, plc_client):
        try:
            future_plc_client = self._plc_clients_by_nad[nad]
            if not future_plc_client.done():
                future_plc_client.set_result(plc_client)
            else:
                self._create_future_and_set_immediately(nad, plc_client)
        except KeyError:
            self._create_future_and_set_immediately(nad, plc_client)

        def log_msg():
            result = f"Added plc client c{nad}"
            if plc_client is not None:
                result += f": {plc_client.plc_info}"
            return result

        self._log.info(log_msg)

    def _remove(self, nad):
        try:
            future_plc_client = self._plc_clients_by_nad[nad]
            future_plc_client.cancel()
        except KeyError:
            pass

        try:
            del self._plc_clients_by_nad[nad]
        except KeyError:
            pass

        self._log.info(f"Removed plc client c{nad}")

    def _create_future_and_set_immediately(self, nad, plc_client):
        future_plc_client = self._loop.create_future()
        self._plc_clients_by_nad[nad] = future_plc_client
        future_plc_client.set_result(plc_client)

    async def _autodetect(self, plc_info):
        try:
            ip = await self._plc_detection_service.detect(plc_info.nad)
            self._plc_info_service.update(plc_info.nad, ip, None, PlcInfo.Origin.AUTO)
        except ExchangerTimeoutError:
            self._remove(plc_info.nad)

    def _create_plc_client(self, plc_info):
        return PlcClient(
            self._client_log,
            self._nad,
            plc_info,
            self._config,
            self._plc_activity_service,
            transaction_id_generator(0, 0xFFFF),
            MAX_FRAME_BYTES,
            self._exchanger,
            self._cpu_intensive_task_runner,
        )
