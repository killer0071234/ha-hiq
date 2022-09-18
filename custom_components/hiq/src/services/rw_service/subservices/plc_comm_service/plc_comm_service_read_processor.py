import functools
from itertools import chain

from .....general.errors import ExchangerTimeoutError
from .....services.rw_service.scgi_communication.r_response import RResponse
from .....services.rw_service.subservices.plc_comm_service.plc_comm_service_request_processor import (
    PlcCommServiceRequestProcessor,
)


class PlcCommServiceReadProcessor(PlcCommServiceRequestProcessor):
    def __init__(
        self, log, client, cpu_intensive_task_runner, on_cache_item_created=None
    ):
        super().__init__(log, client, cpu_intensive_task_runner)
        self._on_cache_item_created = on_cache_item_created

    async def _process_plc_rw_requests(self, requests):
        self._log.debug(lambda: f"Read c{self._nad} begin - {requests}")

        valid = await self._process_valid(
            requests.one_byte, requests.two_byte, requests.four_byte
        )
        invalid = self._process_invalid(requests.invalid)
        responses = valid + invalid

        self._log.debug(lambda: f"Read c{self._nad} succeeded - {len(responses)}")

        return responses

    async def process_cache_item(self, cache_item):
        (requests, command_frame_with_type_info_list) = cache_item

        try:
            values = await self._client.read_random_memory_with_command_frame_and_type_info_list(
                command_frame_with_type_info_list
            )
            return self._create_r_responses_with_success(requests, chain(*values))
        except ExchangerTimeoutError as e:
            self._log.error(
                lambda: f"Read c{self._nad} failed with timeout", exc_info=e
            )

            return self._create_r_responses_with_timeout(requests)

    async def _process_valid(self, one_byte, two_byte, four_byte):
        (
            one_b_addrs,
            two_b_addrs,
            four_b_addrs,
            four_b_types,
        ) = self._prepare_addresses_and_types_blocking(one_byte, two_byte, four_byte)

        requests = list(chain(one_byte, two_byte, four_byte))

        try:
            command_frame_and_type_info_list = []

            def on_command_frame_and_type_info_created(command_frame, type_info):
                command_frame_and_type_info_list.append((command_frame, type_info))

            values = await self._client.read_random_memory(
                one_b_addrs,
                two_b_addrs,
                four_b_addrs,
                four_b_types,
                on_command_frame_and_type_info_created=on_command_frame_and_type_info_created,
            )

            if self._on_cache_item_created is not None:
                self._on_cache_item_created(
                    (requests, command_frame_and_type_info_list)
                )

            return self._create_r_responses_with_success(requests, chain(*values))
        except ExchangerTimeoutError as e:
            self._log.error(
                lambda: f"Read c{self._nad} failed with timeout", exc_info=e
            )

            return self._create_r_responses_with_timeout(requests)

    async def _prepare_addresses_and_types(self, one_byte, two_byte, four_byte):
        return await self._cpu_intensive_task_runner.run(
            functools.partial(
                self._prepare_addresses_and_types_blocking,
                one_byte,
                two_byte,
                four_byte,
            )
        )

    @classmethod
    def _prepare_addresses_and_types_blocking(cls, one_byte, two_byte, four_byte):
        one_b_addrs = [req.alc_data.addr for req in one_byte]
        two_b_addrs = [req.alc_data.addr for req in two_byte]
        four_b_addrs = []
        four_b_types = []
        for request in four_byte:
            four_b_addrs.append(request.alc_data.addr)
            four_b_types.append(request.alc_data.data_type)

        return one_b_addrs, two_b_addrs, four_b_addrs, four_b_types

    @classmethod
    def _process_invalid(cls, invalid):
        return [
            RResponse.create(
                request.name,
                request.var_name,
                str(request.value),
                "",
                False,
                RResponse.Code.UNKNOWN,
            )
            for request in invalid
        ]

    @classmethod
    def _create_r_responses_with_timeout(cls, requests):
        return [
            cls._create_r_response(request, None, RResponse.Code.TIMEOUT)
            for request in requests
        ]

    @classmethod
    def _create_r_responses_with_success(cls, requests, values):
        return [
            cls._create_r_response(request, value, RResponse.Code.NO_ERROR)
            for request, value in zip(requests, values)
        ]

    @classmethod
    def _create_r_response(cls, request, value, code):
        alc_data = request.alc_data
        description = None if alc_data is None else alc_data.description
        is_valid = code == RResponse.Code.NO_ERROR

        return RResponse.create(
            request.name, request.var_name, str(value), description, is_valid, code
        )
