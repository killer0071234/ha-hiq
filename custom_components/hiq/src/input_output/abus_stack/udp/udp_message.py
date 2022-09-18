from dataclasses import dataclass
from typing import Tuple


@dataclass
class UdpMessage:
    data: bytes
    addr: Tuple[str, int]

    def __str__(self):
        (host, port) = self.addr
        return f"{host}:{port} - {self.data.hex()}"
