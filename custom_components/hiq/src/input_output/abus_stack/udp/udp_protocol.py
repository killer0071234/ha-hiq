from asyncio import DatagramProtocol

from ....input_output.abus_stack.udp.udp_message import UdpMessage


class UdpProtocol(DatagramProtocol):
    def __init__(self, log, receiver):
        self._log = log
        self._receiver = receiver
        self._transport = None

    def send(self, udp_msg):
        self._log.debug(f"OUT {udp_msg.addr} {udp_msg.data.hex()}")
        self._transport.sendto(udp_msg.data, udp_msg.addr)

    def receive(self, udp_msg):
        self._log.debug(f"IN {udp_msg.addr} {udp_msg.data.hex()}")
        self._receiver.receive(udp_msg)

    def connection_made(self, transport):
        self._log.debug("Connection established")
        self._transport = transport

    def connection_lost(self, exc):
        self._log.error("Connection lost", exc_info=exc)
        self._transport = None

    def datagram_received(self, data, addr):
        udp_msg = UdpMessage(data, addr)
        self.receive(udp_msg)

    def error_received(self, exc):
        self._log.error("Error received", exc_info=exc)
