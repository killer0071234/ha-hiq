import struct
from dataclasses import dataclass

from ....input_output.abus_stack.abus.errors import AbusError


@dataclass
class TransportFrame:
    signature: int
    length: int
    from_addr: int
    to_addr: int
    data_block_bytes: bytes
    transaction_id: int
    crc: int

    def __str__(self):
        return (
            f"SIG({self.signature}) "
            f"LEN({self.length}) "
            f"ADDR({self.from_addr} -> {self.to_addr}) "
            f"TRAN({self.transaction_id}) "
            f"DATA({self.data_block_bytes.hex()}) "
            f"CRC({self.crc})"
        )


class TransportFrameUtil:
    _struct_signature = struct.Struct("<H")
    _struct_header = struct.Struct("<2H2L")
    _struct_tail = struct.Struct("<2H")
    _struct_transaction_id = struct.Struct("<H")

    SIGNATURE: int = _struct_signature.unpack(b"\xAA\x55")[0]
    HEADER_LENGTH = 12
    TRANSACTION_ID_LENGTH = 2
    CRC_LENGTH = 2
    CRC_PRIM_TABLE = (
        0x049D,
        0x0C07,
        0x1591,
        0x1ACF,
        0x1D4B,
        0x202D,
        0x2507,
        0x2B4B,
        0x34A5,
        0x38C5,
        0x3D3F,
        0x4445,
        0x4D0F,
        0x538F,
        0x5FB3,
        0x6BBF,
    )

    @classmethod
    def create_transport_frame(
        cls, from_addr, to_addr, data_block_bytes, transaction_id
    ):
        transaction_id_bytes = cls._struct_transaction_id.pack(transaction_id)
        length = len(data_block_bytes) + len(transaction_id_bytes)
        header_bytes = cls._struct_header.pack(
            cls.SIGNATURE, length, from_addr, to_addr
        )
        crc = cls._calc_crc(header_bytes + data_block_bytes + transaction_id_bytes)

        return TransportFrame(
            cls.SIGNATURE,
            length,
            from_addr,
            to_addr,
            data_block_bytes,
            transaction_id,
            crc,
        )

    @classmethod
    def transport_frame_to_bytes(cls, transport_frame):
        header = cls._struct_header.pack(
            transport_frame.signature,
            transport_frame.length,
            transport_frame.from_addr,
            transport_frame.to_addr,
        )
        tail = cls._struct_tail.pack(
            transport_frame.transaction_id, transport_frame.crc
        )

        return header + transport_frame.data_block_bytes + tail

    @classmethod
    def bytes_to_transport_frame(cls, transport_frame_bytes):
        if len(transport_frame_bytes) < cls.HEADER_LENGTH:
            raise AbusError("frame shorter than header")

        header_bytes = transport_frame_bytes[: cls.HEADER_LENGTH]
        body_bytes = transport_frame_bytes[cls.HEADER_LENGTH :]

        max_data_block_bytes_length = (
            len(body_bytes) - cls.TRANSACTION_ID_LENGTH - cls.CRC_LENGTH
        )

        (signature, length, from_addr, to_addr) = cls._struct_header.unpack(
            header_bytes
        )

        data_block_bytes_length = length - cls.TRANSACTION_ID_LENGTH

        if data_block_bytes_length > max_data_block_bytes_length:
            raise AbusError(
                f"length is {length} while max possible is {max_data_block_bytes_length}"
            )

        data_block_bytes_length = max_data_block_bytes_length

        data_block_bytes = body_bytes[:data_block_bytes_length]
        tail_bytes = body_bytes[data_block_bytes_length:]

        (transaction_id, crc) = cls._struct_tail.unpack(tail_bytes)

        correct_crc = cls._calc_crc(
            header_bytes + data_block_bytes + tail_bytes[: cls.TRANSACTION_ID_LENGTH]
        )

        if crc != correct_crc:
            raise AbusError("Invalid crc")

        return TransportFrame(
            signature, length, from_addr, to_addr, data_block_bytes, transaction_id, crc
        )

    @classmethod
    def _calc_crc(cls, data):
        crc = 0
        for i, byte in enumerate(data):
            crc += (byte ^ 0x5A) * cls.CRC_PRIM_TABLE[i & 0x0F]

        return crc & 0xFFFF  # cast it to word
