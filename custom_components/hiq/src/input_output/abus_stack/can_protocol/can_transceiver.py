import can


class CanTransceiver(can.Listener):
    def __init__(self, communication_loop, log, config, receiver):
        self._communication_loop = communication_loop
        self._log = log
        self._config = config.can_config
        self._receiver = receiver
        self._receiver.set_sender(self)
        self._notifier = None
        self._bus = None

    def start(self):
        can.rc["interface"] = self._config.interface
        can.rc["channel"] = self._config.channel
        can.rc["bitrate"] = self._config.bitrate
        self._bus = can.interface.Bus()
        self._notifier = can.Notifier(self._bus, [self], loop=self._communication_loop)

    def send(self, can_msg):
        try:
            self._log.info(
                f"Sending: {CanTransceiver._create_can_msg_string_representation(can_msg)}"
            )
            self._bus.send(can_msg)
        except can.CanError:
            self._log.error(
                f"Sending failed: {CanTransceiver._create_can_msg_string_representation(can_msg)}"
            )

    def on_message_received(self, can_msg):
        self._log.info(
            f"Received: {CanTransceiver._create_can_msg_string_representation(can_msg)}"
        )
        self._receiver.receive(can_msg)

    def on_error(self, exc):
        self._log.error(f"Can error: {exc}")

    @staticmethod
    def _create_can_msg_string_representation(can_msg):
        return f"{can_msg.arbitration_id} {can_msg.data.hex()}"
