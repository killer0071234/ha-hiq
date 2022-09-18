import struct
from dataclasses import dataclass
from enum import Enum


class SystemStatus(Enum):
    LOADER_ACTIVE = 0
    KERNEL_ACTIVE = 1


class PlcStatus(Enum):
    STOP = 0
    PAUSE = 1
    RUN = 2
    NO_VALID_PROGRAM = 3
    SCAN_OVERRUN_ERROR = 4


_struct = struct.Struct("<2B")


@dataclass(frozen=True)
class Status:
    system_status: SystemStatus
    plc_status: PlcStatus


def bytes_to_status(data_bytes):
    return _create(*_struct.unpack(data_bytes))


def _create(system_status, plc_status):
    return Status(SystemStatus(system_status), PlcStatus(plc_status))
