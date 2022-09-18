import struct
from dataclasses import dataclass
from datetime import datetime

from .......services.rw_service.subservices.plc_comm_service.plc_client_manager.plc_client.util import (
    cybro_timestamp_to_datetime,
)


@dataclass(frozen=True)
class FileDescriptor:
    SIZE = 46

    name: str
    address: int
    size: int
    timestamp: datetime


_struct = struct.Struct("<32sH3L")


def bytes_to_file_descriptor(data_bytes):
    return _create(*_struct.unpack(data_bytes))


def _create(name, name_len, addr, size, date):
    name = name[:name_len]
    return FileDescriptor(name.decode(), addr, size, cybro_timestamp_to_datetime(date))
