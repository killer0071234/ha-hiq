import asyncio

from ...constants import ABUS_BROADCAST_PORT
from ...constants import MAX_FRAME_BYTES
from ...constants import PUSH_NAD
from ...general.errors import ExchangerTimeoutError
from ...general.transaction_id_generator import transaction_id_generator
from ...input_output.abus_stack.abus.abus_message import AbusMessage
from ...input_output.abus_stack.abus.command_frame import CommandFrameUtil
from ...services.plc_info_service.plc_info import PlcInfo


class PushService:
    def __init__(
        self,
        log,
        loop,
        plc_info_service,
        plc_activity_service,
        push_activity_service,
        config,
    ):
        self._log = log
        self._loop = loop
        self._plc_info_service = plc_info_service
        self._plc_activity_service = plc_activity_service
        self._push_activity_service = push_activity_service
        self._config = config
        self._nad = PUSH_NAD
        self._max_frame_length = MAX_FRAME_BYTES
        self._transaction_id_generator = transaction_id_generator(0, 0xFFFF)

        self._exchanger = None

    def set_exchanger(self, exchanger):
        self._exchanger = exchanger

    def receive(self, abus_msg):
        """communication loop"""
        if abus_msg.is_push:
            asyncio.run_coroutine_threadsafe(self._handle_push(abus_msg), self._loop)

    async def _handle_push(self, abus_msg):
        self._push_activity_service.report_push_request_received()
        self._log.debug(lambda: f"Push from c{abus_msg.from_nad} received")

        plc_nad = abus_msg.from_nad
        (ip, port) = abus_msg.addr
        push_ack_message = self._create_push_ack_message(ip, port, plc_nad)

        try:
            await self._exchanger.exchange_threadsafe(push_ack_message)
            self._push_activity_service.report_push_acknowledgment_succeeded()
            self._plc_info_service.update(
                plc_nad, ip, ABUS_BROADCAST_PORT, PlcInfo.Origin.PUSH
            )
            self._log.debug(lambda: f"Push from c{plc_nad} acknowledged")
        except ExchangerTimeoutError as e:
            self._push_activity_service.report_push_acknowledgment_failed()
            self._log.error(
                lambda: f"Push from c{plc_nad} acknowledgment failed with timeout",
                exc_info=e,
            )

    def _create_push_ack_message(self, ip, port, nad):
        addr = (ip, port)
        transaction_id = next(self._transaction_id_generator)
        command_frame = CommandFrameUtil.create_push_ack()
        return AbusMessage(addr, self._nad, nad, transaction_id, command_frame)
