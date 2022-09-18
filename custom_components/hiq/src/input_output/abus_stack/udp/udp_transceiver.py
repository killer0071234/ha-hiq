import asyncio
import socket

from .udp_protocol import UdpProtocol


class UdpTransceiver:
    def __init__(
        self,
        log,
        main_loop,
        communication_loop,
        transceiver,
        udp_activity_service,
        config,
    ):
        self._log = log
        self._main_loop = main_loop
        self._communication_loop = communication_loop
        self._transceiver = transceiver
        self._transceiver.set_udp_sender(self)
        self._udp_activity_service = udp_activity_service
        self._abus_config = config.abus_config
        self._eth_config = config.eth_config

        self._bind_addr = None
        self._sender = None

    async def start(self):
        transport, _ = await asyncio.wrap_future(
            asyncio.run_coroutine_threadsafe(self._start(), self._communication_loop)
        )

        self._bind_addr = transport.get_extra_info("socket").getsockname()
        host, port = self._bind_addr
        self._log.info(lambda: f"Listening on {host}:{port}")

        return self._bind_addr

    async def _start(self):
        """communication loop"""

        def protocol_factory():
            protocol = UdpProtocol(self._log, self)
            self._sender = protocol
            return protocol

        return await asyncio.get_running_loop().create_datagram_endpoint(
            protocol_factory=protocol_factory,
            local_addr=(self._eth_config.bind_address, self._eth_config.port),
            allow_broadcast=True,
            family=socket.AF_INET,
        )

    def send(self, udp_msg):
        """communication loop"""
        self._udp_activity_service.report_tx()
        self._sender.send(udp_msg)

    def receive(self, udp_msg):
        """communication loop"""
        if udp_msg.addr != self._bind_addr:
            self._udp_activity_service.report_rx()
            self._transceiver.receive(udp_msg)
