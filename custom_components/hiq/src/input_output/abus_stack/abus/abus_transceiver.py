from ....input_output.abus_stack.abus.abus_message import AbusMessageUtil
from ....input_output.abus_stack.abus.errors import AbusError
from ....input_output.abus_stack.can_protocol.iex_frame import IexFrame
from ....input_output.abus_stack.udp.udp_message import UdpMessage


class AbusTransceiver:
    def __init__(self, log, receiver, config):
        self._config = config

        self._log = log
        self._receiver = receiver
        self._receiver.set_sender(self)
        self._udp_sender = None
        self._iex_sender = None

    def set_udp_sender(self, sender):
        self._udp_sender = sender

    def set_can_sender(self, sender):
        self._iex_sender = sender

    def send(self, abus_msg):
        """communication loop"""

        if abus_msg.addr == ("0.0.0.0", 0) and self._config.can_config.enabled:
            self._send_via_iex(abus_msg)

        elif self._config.eth_config.enabled:
            self._send_via_udp(abus_msg)

    def receive(self, msg):
        """communication loop"""

        if isinstance(msg, UdpMessage):
            self._receive_udp_msg(msg)
        else:
            self._receive_iex_frames(msg)

    def _send_via_udp(self, abus_msg):
        """communication loop"""

        self._log.debug(lambda: f"Send UDP: {abus_msg}")
        udp_msg = self._abus_msg_to_udp_msg(abus_msg)
        self._udp_sender.send(udp_msg)

    def _send_via_iex(self, abus_msg):
        """communication loop"""

        self._log.debug(lambda: f"Send CAN: {abus_msg}")
        iex_frames = AbusTransceiver.abus_bytes_to_iex_frames(abus_msg)
        self._iex_sender.send(iex_frames)

    def _receive_udp_msg(self, udp_msg):
        """communication loop"""

        abus_msg = self._udp_msg_to_abus_msg(udp_msg)
        if abus_msg is not None:
            self._log.debug(lambda: f"Receive UDP: {abus_msg}")
            self._receiver.receive(abus_msg)

    def _receive_iex_frames(self, iex_frames):
        """communication loop"""

        abus_msg = self._iex_frames_to_abus_msg(iex_frames)
        if abus_msg is not None:
            self._log.debug(lambda: f"Receive CAN: {abus_msg}")
            self._receiver.receive(abus_msg)

    @classmethod
    def _abus_msg_to_udp_msg(cls, abus_msg):
        """communication loop"""
        return AbusMessageUtil.abus_msg_to_udp_msg(abus_msg)

    def _udp_msg_to_abus_msg(self, udp_msg):
        """communication loop"""
        try:
            return AbusMessageUtil.udp_msg_to_abus_msg(udp_msg)
        except AbusError as e:
            self._log.error(f"Received invalid data\n{udp_msg}", exc_info=e)

    def _iex_frames_to_abus_msg(self, iex_frames):
        """communication loop"""
        try:
            return AbusMessageUtil.iex_frame_to_abus_msg(iex_frames)
        except AbusError as e:
            self._log.error(f"Received invalid data\n{iex_frames}", exc_info=e)

    @classmethod
    def abus_bytes_to_iex_frames(cls, abus_msg):
        iex_frames_list = []
        abus_bytes = AbusMessageUtil.abus_msg_to_bytes(abus_msg)
        while len(abus_bytes) > 8:
            chunk = abus_bytes[0:8]
            iex_frames_list.append(
                IexFrame.create_abus_stream_out(address=0, data=chunk)
            )
            abus_bytes = abus_bytes[8:]
        else:
            iex_frames_list.append(
                IexFrame.create_abus_strend_out(address=0, data=abus_bytes)
            )

        return iex_frames_list
