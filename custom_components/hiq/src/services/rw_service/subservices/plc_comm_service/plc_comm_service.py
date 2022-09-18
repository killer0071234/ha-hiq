import asyncio
from itertools import chain

from .....general.errors import ExchangerTimeoutError
from .....general.misc import create_task_callback
from .....general.unzip import unzip
from .....services.rw_service.scgi_communication.r_response import RResponse
from .....services.rw_service.subservices.plc_comm_service.plc_cache.plc_cache_facade import (
    PlcCacheFacade,
)
from .....services.rw_service.subservices.plc_comm_service.plc_communicator import (
    PlcCommunicator,
)


class PlcCommService:
    def __init__(
        self,
        log,
        plc_info_service,
        alc_service,
        plc_activity_service,
        plc_client_manager,
        plc_cache,
        data_logger_cache,
        cpu_intensive_task_runner,
        config,
    ):
        self._log = log
        self._plc_info_service = plc_info_service
        self._alc_service = alc_service
        self._plc_activity_service = plc_activity_service
        self._plc_client_manager = plc_client_manager
        self._cache = plc_cache
        self._data_logger_cache = data_logger_cache
        self._cpu_intensive_task_runner = cpu_intensive_task_runner
        self._config = config

    def set_exchanger(self, exchanger):
        self._plc_client_manager.set_exchanger(exchanger)

    async def process_rw_requests(self, nad, r_requests, w_requests, task_id):
        responses = await self._process_rw_requests(
            nad, r_requests, w_requests, task_id
        )
        self._log.debug(lambda: f"RW Results c{nad} - {len(responses)} responses")
        return responses

    async def _process_rw_requests(self, nad: int, r_requests, w_requests, task_id):
        plc_client = await self._plc_client_manager.get(nad)

        if plc_client is None or not plc_client.plc_info.has_ip:
            return [
                RResponse.create(
                    request.name,
                    request.tag_name,
                    request.value,
                    "",
                    False,
                    RResponse.Code.DEVICE_NOT_FOUND,
                )
                for request in r_requests
            ]

        if self._cache is None:
            cache_facade = None
        else:
            cache_facade = PlcCacheFacade(self._log, self._cache[nad])

        plc_communicator = PlcCommunicator(
            self._log,
            plc_client,
            cache_facade,
            self._plc_activity_service,
            self._get_alc,
            self._update_plc_client_datetime,
            self._update_plc_client_ip,
            self._cpu_intensive_task_runner,
            self._data_logger_cache,
        )

        if task_id is not None:
            if len(w_requests) > 0:
                # sanity check
                self._log.error(
                    f"{len(w_requests)} write requests came from the data logger. They will be "
                    f"ignored."
                )
            return await plc_communicator.process_r_requests_for_data_logger(
                r_requests, task_id
            )

        if len(w_requests) > 0:
            return await plc_communicator.process_rw_requests(r_requests, w_requests)

        if cache_facade is None:
            return await plc_communicator.process_rw_requests(r_requests, [])
        else:
            cache_result = await cache_facade.read(r_requests)

            responses = list(
                chain(cache_result.fresh.values(), cache_result.stinky.values())
            )
            postponable_requests = list(cache_result.stinky.keys())
            urgent_requests = list(cache_result.not_available)

        if len(postponable_requests) > 0:
            self._log.debug("Fetch postponable")
            asyncio.get_running_loop().create_task(
                plc_communicator.process_rw_requests(postponable_requests, [])
            ).add_done_callback(create_task_callback(self._log))

        if len(urgent_requests) > 0:
            responses += await plc_communicator.process_rw_requests(urgent_requests, [])

        return responses

    async def _get_alc(self, plc_client, crc):
        try:
            return self._alc_service[crc]
        except KeyError:
            pass

        try:
            self._log.info(
                lambda: f"New crc for c{plc_client.plc_info.nad}: {crc}. Reload alc..."
            )
            await self._fetch_alc_and_save(plc_client, crc)
            return self._alc_service[crc]
        except ExchangerTimeoutError:
            return None

    async def _fetch_alc_and_save(self, plc_client, crc):
        alc_bytes_zipped = await plc_client.fetch_alc_file()
        alc_bytes = await unzip(alc_bytes_zipped)
        alc_text = alc_bytes.decode("latin-1")
        self._alc_service.set_alc_text(alc_text, crc)

    async def _update_plc_client_datetime(self, plc_client, program_datetime):
        nad = plc_client.plc_info.nad
        self._plc_info_service.update_program_datetime(nad, program_datetime)
        return await self._plc_client_manager.get(nad)

    async def _update_plc_client_ip(self, plc_client):
        # deleting and requesting plc_info will implicitly trigger ip detection
        nad = plc_client.plc_info.nad
        await self._plc_info_service.remove_plc_info(nad)
        return await self._plc_client_manager.get(nad)
