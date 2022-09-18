import struct
from datetime import timedelta
from functools import reduce
from timeit import default_timer

from .......general.errors import ExchangerTimeoutError
from .......general.misc import chunk
from .......input_output.abus_stack.abus.abus_message import AbusMessage
from .......input_output.abus_stack.abus.command_frame import CommandFrameUtil
from .......input_output.abus_stack.abus.transport_frame import TransportFrameUtil
from .......services.rw_service.subservices.plc_comm_service.data_type import DataType
from .......services.rw_service.subservices.plc_comm_service.plc_client_manager.plc_client.file_descriptor import (
    bytes_to_file_descriptor,
)
from .......services.rw_service.subservices.plc_comm_service.plc_client_manager.plc_client.file_descriptor import (
    FileDescriptor,
)
from .......services.rw_service.subservices.plc_comm_service.plc_client_manager.plc_client.plc_client_read_write_util import (
    PlcClientReadWriteUtil,
)
from .......services.rw_service.subservices.plc_comm_service.plc_client_manager.plc_client.plc_head import (
    bytes_to_plc_head,
)
from .......services.rw_service.subservices.plc_comm_service.plc_client_manager.plc_client.status import (
    bytes_to_status,
)


class PlcClient:
    PLC_HEAD_MEMORY_SEGMENT = 0x0200
    FILE_DESCRIPTORS_INFO_SEGMENT = 0x20040

    PLC_HEAD_SIZE = 0x46
    FILE_DESCRIPTORS_INFO_SIZE = 6

    SEGMENT_SIZE = 0x100

    TRANSPORT_LAYER_AND_COMMAND_HEAD_AND_COMMAND = (
        TransportFrameUtil.HEADER_LENGTH
        + TransportFrameUtil.TRANSACTION_ID_LENGTH
        + TransportFrameUtil.CRC_LENGTH
        + CommandFrameUtil.HEAD_LENGTH
        + CommandFrameUtil.COMMAND_LENGTH
    )

    def __init__(
        self,
        log,
        nad,
        plc_info,
        config,
        plc_activity_service,
        transaction_id_generator,
        max_frame_length,
        exchanger,
        cpu_intensive_task_runner,
    ):
        self._log = log
        self._nad = nad
        self._plc_info = plc_info
        self._config = config
        self._plc_activity_service = plc_activity_service
        self._transaction_id_generator = transaction_id_generator
        self._rw_util = PlcClientReadWriteUtil(max_frame_length)
        self._exchanger = exchanger
        self._cpu_intensive_task_runner = cpu_intensive_task_runner

    @property
    def plc_info(self):
        return self._plc_info

    @property
    def has_ip(self):
        ip, port = self._addr
        return ip is not None

    @property
    def _addr(self):
        return self._plc_info.ip, self._plc_info.port

    async def _send_and_extract_command(self, command_frame):
        response = await self._send(command_frame)
        return response.command_frame

    async def _send(self, command_frame):
        request = self._create_request(command_frame)
        # abus_config = self._config.abus_config

        try:
            self._plc_activity_service.report_exchange_initiated(self._plc_info.nad)

            start = default_timer()
            response = await self._exchanger.exchange_threadsafe(request)

            self._plc_activity_service.report_exchange_succeeded(
                self._plc_info.nad,
                request.size + response.size,
                timedelta(seconds=default_timer() - start),
            )

            return response
        except ExchangerTimeoutError as e:
            self._plc_activity_service.report_exchange_failed(self._plc_info.nad)
            raise e

    def _create_request(self, command_frame):
        transaction_id = (
            self._plc_info.password
            if self._plc_info.has_password
            else next(self._transaction_id_generator)
        )
        return AbusMessage(
            self._addr, self._nad, self._plc_info.nad, transaction_id, command_frame
        )

    async def ping(self):
        return await self._send_and_extract_command(CommandFrameUtil.create_ping())

    async def acknowledge_push(self):
        return await self._send_and_extract_command(CommandFrameUtil.create_push_ack())

    async def fetch_alc_file(self):
        (
            file_descriptors_addr,
            file_count,
        ) = await self.read_file_descriptors_addr_and_file_count()

        file_descriptors = await self.read_file_descriptors(
            file_descriptors_addr, file_count
        )
        alc_file_descriptor = next(
            fd for fd in file_descriptors if fd.name == "alc.zip"
        )

        alc_file = await self._read_code_memory(
            alc_file_descriptor.address, alc_file_descriptor.size
        )

        return alc_file

    async def read_plc_head(self):
        try:
            response = await self._send_and_extract_command(
                CommandFrameUtil.create_read_code_memory_block(
                    self.PLC_HEAD_MEMORY_SEGMENT, self.PLC_HEAD_SIZE
                )
            )
            plc_head = bytes_to_plc_head(response.body_bytes)
            self._plc_activity_service.report_plc_head_used(
                self._plc_info.nad, plc_head
            )
            return plc_head
        except ExchangerTimeoutError as e:
            self._plc_activity_service.report_plc_head_used(self._plc_info.nad, None)
            raise e

    async def read_file_descriptors(self, file_descriptors_addr, file_count):
        size = file_count * FileDescriptor.SIZE
        file_descriptors_bytes = await self._read_code_memory(
            file_descriptors_addr, size
        )

        result = []

        for i in range(file_count):
            from_byte = i * FileDescriptor.SIZE
            to_byte = from_byte + FileDescriptor.SIZE
            file_descriptor = bytes_to_file_descriptor(
                file_descriptors_bytes[from_byte:to_byte]
            )
            result.append(file_descriptor)

        return result

    async def read_file_descriptors_addr_and_file_count(self):
        file_descriptors_info_bytes = await self._read_code_memory(
            self.FILE_DESCRIPTORS_INFO_SEGMENT, self.FILE_DESCRIPTORS_INFO_SIZE
        )

        return struct.unpack("<LH", file_descriptors_info_bytes)

    async def read_status(self):
        command = CommandFrameUtil.create_read_status()
        try:
            response = await self._send_and_extract_command(command)
        except ExchangerTimeoutError as e:
            self._plc_activity_service.report_plc_status_used(self._plc_info.nad, None)
            raise e

        status = bytes_to_status(response.body_bytes)
        self._plc_activity_service.report_plc_status_used(
            self._plc_info.nad, status.plc_status
        )
        return status

    async def read_random_memory(
        self,
        one_b_addrs,
        two_b_addrs,
        four_b_addrs,
        four_b_types,
        on_command_frame_and_type_info_created,
    ):
        self._log.debug(
            lambda: f"Read bulk {len(one_b_addrs)}, {len(two_b_addrs)}, {len(four_b_addrs)} "
            f"(1B, 2B, 4B)"
        )

        params_to_use, params_left = await self._cpu_intensive_task_runner.run(
            self._rw_util.split_r_random_memory_params,
            (one_b_addrs, two_b_addrs, four_b_addrs, four_b_types),
        )

        results = await self._read_random_memory_single_request(
            *params_to_use,
            on_command_frame_and_type_info_created=on_command_frame_and_type_info_created,
        )
        if params_left is None:
            return results
        else:
            rest_results = await self.read_random_memory(
                *params_left,
                on_command_frame_and_type_info_created=on_command_frame_and_type_info_created,
            )

            return await self._cpu_intensive_task_runner.run(
                PlcClientReadWriteUtil.merge_r_random_memory_results,
                results,
                rest_results,
            )

    async def read_random_memory_with_command_frame_and_type_info_list(
        self, command_frame_and_type_info_list
    ):
        previous_results = ([], [], [])

        for (command_frame, type_info) in command_frame_and_type_info_list:
            new_results = await self.read_random_memory_with_command_frame_and_type_info_single_request(
                command_frame, type_info
            )

            previous_results = await self._cpu_intensive_task_runner.run(
                PlcClientReadWriteUtil.merge_r_random_memory_results,
                previous_results,
                new_results,
            )

        return previous_results

    async def _read_random_memory_single_request(
        self,
        one_b_addrs,
        two_b_addrs,
        four_b_addrs,
        four_b_types,
        on_command_frame_and_type_info_created,
    ):
        self._log.debug(
            lambda: f"Read {len(one_b_addrs)}, {len(two_b_addrs)}, {len(four_b_addrs)} "
            f"(1B, 2B, 4B)"
        )

        one_b_items_count = len(one_b_addrs)
        two_b_items_count = len(two_b_addrs)
        four_b_items_count = len(four_b_addrs)

        command_frame = CommandFrameUtil.create_read_random_memory(
            one_b_addrs, two_b_addrs, four_b_addrs
        )

        type_info = (
            one_b_items_count,
            two_b_items_count,
            four_b_items_count,
            four_b_types,
        )

        if on_command_frame_and_type_info_created is not None:
            on_command_frame_and_type_info_created(command_frame, type_info)

        return await self.read_random_memory_with_command_frame_and_type_info_single_request(
            command_frame, type_info
        )

    async def read_random_memory_with_command_frame_and_type_info_single_request(
        self, command_frame, type_info
    ):
        (
            one_b_items_count,
            two_b_items_count,
            four_b_items_count,
            four_b_types,
        ) = type_info

        response = await self._send_and_extract_command(command_frame)

        one_b_values_b_size = one_b_items_count
        two_b_values_b_size = two_b_items_count * 2
        four_b_values_b_size = four_b_items_count * 4

        one_b_values_b_offset = 0
        two_b_values_b_offset = one_b_values_b_size
        four_b_values_b_offset = one_b_values_b_size + two_b_values_b_size

        one_b_values_bytes = response.body_bytes[
            one_b_values_b_offset:two_b_values_b_offset
        ]
        two_b_values_bytes = response.body_bytes[
            two_b_values_b_offset:four_b_values_b_offset
        ]
        four_b_values_bytes = response.body_bytes[
            four_b_values_b_offset : four_b_values_b_offset + four_b_values_b_size
        ]

        one_b_values = struct.unpack(f"<{one_b_items_count}B", one_b_values_bytes)
        two_b_values = struct.unpack(f"<{two_b_items_count}h", two_b_values_bytes)

        four_b_values = []

        for i, value_bytes in enumerate(chunk(four_b_values_bytes, 4)):
            data_type = four_b_types[i]
            if data_type == DataType.REAL:
                four_b_values.append(struct.unpack("<f", value_bytes)[0])
            else:
                four_b_values.append(struct.unpack("<l", value_bytes)[0])

        return one_b_values, two_b_values, four_b_values

    async def write_random_memory(
        self,
        one_b_addrs,
        two_b_addrs,
        four_b_addrs,
        one_b_values,
        two_b_values,
        four_b_values,
        four_b_types,
    ):
        self._log.debug(
            lambda: f"Write bulk {len(one_b_addrs)}, {len(two_b_addrs)}, {len(four_b_addrs)} "
            f"(1B, 2B, 4B)"
        )

        params_to_use, params_left = await self._cpu_intensive_task_runner.run(
            self._rw_util.split_w_random_memory_params,
            (
                one_b_addrs,
                two_b_addrs,
                four_b_addrs,
                one_b_values,
                two_b_values,
                four_b_values,
                four_b_types,
            ),
        )

        await self._write_random_memory_single_request(*params_to_use)
        if params_left is not None:
            await self.write_random_memory(*params_left)

    async def _write_random_memory_single_request(
        self,
        one_b_addrs,
        two_b_addrs,
        four_b_addrs,
        one_b_values,
        two_b_values,
        four_b_values,
        four_b_types,
    ):
        self._log.debug(
            lambda: f"Write {len(one_b_addrs)}, {len(two_b_addrs)}, {len(four_b_addrs)} "
            f"(1B, 2B, 4B)"
        )

        one_b_values_bytes = struct.pack(f"<{len(one_b_values)}B", *one_b_values)
        two_b_values_bytes = struct.pack(f"<{len(two_b_values)}h", *two_b_values)

        def generate_four_byte_values_bytes():
            for value, data_type in zip(four_b_values, four_b_types):
                if data_type == DataType.REAL:
                    yield struct.pack("<f", value)
                else:
                    yield struct.pack("<l", value)

        request = CommandFrameUtil.create_write_random_memory(
            one_b_addrs,
            two_b_addrs,
            four_b_addrs,
            one_b_values_bytes,
            two_b_values_bytes,
            reduce(lambda x, y: x + y, generate_four_byte_values_bytes(), b""),
        )
        await self._send_and_extract_command(request)

    async def _read_code_memory_block(self, segment_number: int, size: int):
        command_frame = CommandFrameUtil.create_read_code_memory_block(
            segment_number, size
        )
        return await self._send_and_extract_command(command_frame)

    async def _read_code_memory(self, addr: int, size: int) -> bytes:
        result = b""
        for segment_number, offset, size in self._generate_read_info(addr, size):
            command_frame = await self._read_code_memory_block(segment_number, size)
            result += command_frame.body_bytes[offset:size]

        return result

    def _generate_read_info(self, addr: int, size: int):
        """
        For specified address and data size generate tuples with information required to read each
        particular segment: (segment_number, offset, size).

        Each segment can be read read using `_read_code_memory_block`
        """

        first_segment_number = int(addr / self.SEGMENT_SIZE)
        first_offset = addr % self.SEGMENT_SIZE
        last_segment_number = int((addr + size) / self.SEGMENT_SIZE)
        last_size = (first_offset + size) % self.SEGMENT_SIZE

        for segment_number in range(first_segment_number, last_segment_number + 1):
            offset = first_offset if segment_number == first_segment_number else 0
            size = (
                last_size
                if segment_number == last_segment_number
                else self.SEGMENT_SIZE
            )
            yield segment_number, offset, size
