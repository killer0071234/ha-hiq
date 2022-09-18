import can

from .iex_frame import IexFrame


class IexTransceiver:
    def __init__(self, log, receiver):
        self._log = log
        self._buffer = []
        self._receiver = receiver
        self._receiver.set_can_sender(self)
        self._sender = None

    def set_sender(self, sender):
        self._sender = sender

    def send(self, iex_frames):
        for frame in iex_frames:
            can_msg = IexTransceiver.iex_frame_to_can_msg(frame)
            self._sender.send(can_msg)

    def receive(self, can_msg):
        header = can_msg.arbitration_id.to_bytes(4, byteorder="big")
        data = can_msg.data
        iex_frame = IexFrame.bytes_to_iex(header, data)

        if not (iex_frame.is_stream or iex_frame.is_strend):
            return

        if not iex_frame.is_abus:
            return

        if len(self._buffer) == 0 and not iex_frame.is_data_abus_start:
            return

        if iex_frame.is_stream:
            self.add_to_buffer(iex_frame)
        if iex_frame.is_strend:
            self.add_to_buffer(iex_frame)
            buffer = self._buffer
            self.clear_buffer()

            self._log.debug("Flushing input buffer containing iex frames")
            for iex_frame in buffer:
                self._log.debug(f"{iex_frame}\n")

            self._receiver.receive(buffer)

    @classmethod
    def iex_frame_to_can_msg(cls, iex_frame):
        header, data = IexFrame.iex_to_bytes(iex_frame)

        can_msg = can.Message(
            check=True,
            arbitration_id=int.from_bytes(header, "big"),
            data=bytearray(data),
            is_extended_id=True,
            is_error_frame=False,
            is_remote_frame=False,
        )
        return can_msg

    def add_to_buffer(self, iex_frame):
        self._buffer.append(iex_frame)

    def clear_buffer(self):
        self._buffer = []
