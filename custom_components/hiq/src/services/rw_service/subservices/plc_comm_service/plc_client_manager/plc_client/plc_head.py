import struct
from dataclasses import dataclass
from datetime import datetime

from .......services.rw_service.subservices.plc_comm_service.plc_client_manager.plc_client.util import (
    cybro_timestamp_to_datetime,
)


@dataclass(frozen=True)
class PlcHead:
    empty: int
    magic: int
    crc: int
    code_crc: int
    alloc_crc: int
    retentive_crc: int
    program_timestamp: datetime

    file_system_addr: int
    file_count: int

    scan_overrun: int

    def __str__(self):
        return (
            f"empty={self.empty}, magic={self.magic}, crc={self.crc}, "
            f"code_crc={self.code_crc}, alloc_crc={self.alloc_crc}, "
            f"retentive_crc={self.retentive_crc}, "
            f"program_timestamp={self.program_timestamp}, "
            f"file_system_addr={self.file_system_addr}, "
            f"file_count={self.file_count},"
            f"scan_overrun={self.scan_overrun}"
        )


HEAD_OFFSET = 0
HEAD_SIZE = 0x10

FILE_SYSTEM_INFO_OFFSET = 0x40
FILE_SYSTEM_INFO_SIZE = 4 + 2

SCAN_OVERRUN_OFFSET = 0x38
SCAN_OVERRUN_SIZE = 2

# 16-bit alloc_crc
_struct_head = struct.Struct("<6HL")

# !!! zamjeniti ako se koristi 32-bitni alloc_crc
# !!! obrisati sva pojavljivanja retentive_crc
# _struct_head = struct.Struct("<4H2L")

_struct_file_system_info = struct.Struct("<LH")
_struct_scan_overrun = struct.Struct("<H")


def bytes_to_plc_head(data_bytes):
    head_bytes = data_bytes[HEAD_OFFSET : HEAD_OFFSET + HEAD_SIZE]
    file_system_info_bytes = data_bytes[
        FILE_SYSTEM_INFO_OFFSET : FILE_SYSTEM_INFO_OFFSET + FILE_SYSTEM_INFO_SIZE
    ]

    scan_overrun_bytes = data_bytes[
        SCAN_OVERRUN_OFFSET : SCAN_OVERRUN_OFFSET + SCAN_OVERRUN_SIZE
    ]

    head_values = _struct_head.unpack(head_bytes)
    file_system_values = _struct_file_system_info.unpack(file_system_info_bytes)
    (scan_overrun,) = _struct_scan_overrun.unpack(scan_overrun_bytes)

    return _create(*head_values, *file_system_values, scan_overrun)


def _create(
    empty,
    magic,
    crc,
    code_crc,
    alloc_crc,
    retentive_crc,
    timestamp,
    file_system_addr,
    file_count,
    scan_overrun,
):
    return PlcHead(
        empty,
        magic,
        crc,
        code_crc,
        alloc_crc,
        retentive_crc,
        cybro_timestamp_to_datetime(timestamp),
        file_system_addr,
        file_count,
        scan_overrun,
    )
