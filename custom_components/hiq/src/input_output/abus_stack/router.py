from ...constants import AUTODETECT_NAD
from ...constants import PUSH_NAD
from ...constants import RW_NAD
from .abus.abus_exchanger import AbusExchanger


class Router:
    """
    Routes received abus messages by destination nad to designated receivers.
    """

    def __init__(
        self,
        log,
        communication_loop,
        push_service,
        detection_service,
        rw_service,
        config,
        proxy_service,
    ):
        self._log = log
        self._sender = None
        self._receivers_by_nad = {}
        self._proxy_service = None

        if config.relay_config.relay_enabled:
            self._proxy_service = proxy_service
            proxy_service.set_router(self)

        if config.push_config.enabled:
            push_exchanger = AbusExchanger(
                communication_loop,
                self,
                config.abus_config.timeout_ms,
                config.abus_config.number_of_retries,
            )
            self._receivers_by_nad[PUSH_NAD] = push_exchanger
            push_service.set_exchanger(push_exchanger)
            self._receivers_by_nad[0] = push_service

        detection_exchanger = AbusExchanger(
            communication_loop,
            self,
            config.abus_config.timeout_ms,
            config.abus_config.number_of_retries,
        )
        self._receivers_by_nad[AUTODETECT_NAD] = detection_exchanger
        detection_service.set_exchanger(detection_exchanger)

        rw_exchanger = AbusExchanger(
            communication_loop,
            self,
            config.abus_config.timeout_ms,
            config.abus_config.number_of_retries,
        )
        self._receivers_by_nad[RW_NAD] = rw_exchanger
        rw_service.set_exchanger(rw_exchanger)

    def set_sender(self, sender):
        self._sender = sender

    def send(self, abus_msg):
        """communication loop"""
        self._sender.send(abus_msg)

    def receive(self, abus_msg):
        """communication loop"""

        if abus_msg.to_nad == 0 and not abus_msg.is_push:
            self._handle_proxy_msg(abus_msg)
            return

        try:
            self._receivers_by_nad[abus_msg.to_nad].receive(abus_msg)
        except KeyError:
            self._handle_proxy_msg(abus_msg)

    def _handle_proxy_msg(self, abus_msg):
        """communication loop"""

        if self._proxy_service is not None:
            self._proxy_service.receive(abus_msg)
