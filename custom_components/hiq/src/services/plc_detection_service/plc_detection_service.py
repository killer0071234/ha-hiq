from typing import Optional

from ...constants import ABUS_BROADCAST_PORT
from ...constants import AUTODETECT_NAD
from ...errors import ScgiServerError
from ...general.errors import ExchangerTimeoutError
from ...general.transaction_id_generator import transaction_id_generator
from ...input_output.abus_stack.abus.abus_message import AbusMessage
from ...input_output.abus_stack.abus.command_frame import CommandFrameUtil


class PlcDetectionService:
    def __init__(self, log, plc_info_service, config):
        self._log = log
        self._config = config
        self._plc_info_service = plc_info_service
        self._nad = AUTODETECT_NAD
        self._transaction_id_generator = transaction_id_generator(0, 0xFFFF)
        self._exchanger = None

    def set_exchanger(self, exchanger):
        self._exchanger = exchanger

    async def detect(self, nad):
        try:
            self._log.info(lambda: f"Detecting ip for c{nad}")
            ip = await self._ping_and_get_ip(nad)
            self._log.info(lambda: f"Detected ip {ip} for c{nad}")
            return ip
        except ExchangerTimeoutError as e:
            self._log.warning(lambda: f"Couldn't detect ip for c{nad}")
            raise e

    async def _ping_and_get_ip(self, nad: int) -> Optional[str]:
        plc_info = self._plc_info_service.get_plc_info(nad)

        error = None

        if (
            self._config.eth_config.enabled
            and self._config.eth_config.autodetect_enabled
        ):
            ping_msg = self._create_broadcast_ping_message(plc_info)
            try:
                return await self._detect_with_ping_message(ping_msg)
            except ExchangerTimeoutError as e:
                error = e

        if self._config.can_config.enabled:
            ping_msg = self._create_zero_ping_message(plc_info)
            try:
                return await self._detect_with_ping_message(ping_msg)
            except ExchangerTimeoutError as e:
                error = e

        if error is None:
            error = ScgiServerError(
                "Autodetect failed because following conditions are not satisfied: CAN: enabled or (ETH: enabled and autodetect_enabled)"
            )

        raise error

    async def _detect_with_ping_message(self, ping_msg):
        response = await self._exchanger.exchange_threadsafe(ping_msg)
        ip, port = response.addr

        return ip

    def _create_zero_ping_message(self, plc_info):
        address = ("0.0.0.0", 0)
        return self._create_ping_message_with_address(plc_info, address)

    def _create_broadcast_ping_message(self, plc_info):
        address = (self._config.eth_config.autodetect_address, ABUS_BROADCAST_PORT)
        return self._create_ping_message_with_address(plc_info, address)

    def _create_ping_message_with_address(self, plc_info, address):
        return AbusMessage(
            address,
            self._nad,
            plc_info.nad,
            self._get_transaction_id(plc_info),
            CommandFrameUtil.create_ping(),
        )

    def _get_transaction_id(self, plc_info):
        password = plc_info.password
        return next(self._transaction_id_generator) if password is None else password
