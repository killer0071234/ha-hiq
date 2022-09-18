import struct
from dataclasses import dataclass
from enum import Enum

from .errors import AbusError


class Command(Enum):
    PING = 0x10
    READ_STATUS = 0x11
    READ_CODE = 0x21
    WRITE_DATA = 0x32
    READ_RANDOM = 0x33
    WRITE_RANDOM = 0x34


class Direction(Enum):
    REQ = 0
    ACK = 1
    INTERNAL = 2
    BAD_CMD = 3
    BAD_PARA = 4
    NOT_READY = 5
    NO_PROG = 6
    NO_KERN = 7
    NO_SIGN = 8
    NO_AUTH = 9
    FORCED = 10
    BAD_FLASH = 11
    DENIED = 12


class Type(Enum):
    COMMAND = 0x00
    BROADCAST = 0x64


@dataclass(frozen=True)
class CommandFrame:
    MSG_TYPE_COMMAND = 0

    msg_direction: Direction
    msg_type: int
    body_bytes: bytes

    @property
    def size(self):
        return (
            CommandFrameUtil.HEAD_LENGTH
            + CommandFrameUtil.COMMAND_LENGTH
            + len(self.body_bytes)
        )

    def __str__(self):
        cmd_str = "CMD" if self.msg_type == 0 else f"SOCKET({self.msg_type})"
        body_str = (
            f"{self.body_bytes.hex()}" if (len(self.body_bytes) > 0) else "no data"
        )
        return f"{self.msg_direction.name} {cmd_str} {body_str}"


class CommandFrameUtil:
    _struct_head = struct.Struct("<2B")

    HEAD_LENGTH = 2
    COMMAND_LENGTH = 1
    PUSH_ACK_ADDRESS = 0x0417

    @classmethod
    def create_ping(cls):
        return cls._create_request_with_command(Command.PING)

    @classmethod
    def create_autodetect_response(cls):
        return CommandFrame(Direction.ACK, CommandFrame.MSG_TYPE_COMMAND, b"")

    @classmethod
    def create_push_ack(cls):
        data = struct.pack("<2H", cls.PUSH_ACK_ADDRESS, 1)
        return cls._create_request_with_command(Command.WRITE_DATA, data)

    @classmethod
    def create_read_status(cls):
        return cls._create_request_with_command(Command.READ_STATUS)

    @classmethod
    def create_read_code_memory_block(cls, segment_number, block_size):
        data = struct.pack("<2H", segment_number, block_size)
        return cls._create_request_with_command(Command.READ_CODE, data)

    @classmethod
    def create_read_random_memory(cls, one_byte_addr, two_byte_addr, four_byte_addr):
        counts_bytes = struct.pack(
            "<3H", len(one_byte_addr), len(two_byte_addr), len(four_byte_addr)
        )
        addresses = one_byte_addr + two_byte_addr + four_byte_addr
        addresses_bytes = struct.pack(f"<{len(addresses)}H", *addresses)

        body_bytes = counts_bytes + addresses_bytes

        return cls._create_request_with_command(Command.READ_RANDOM, body_bytes)

    @classmethod
    def create_write_random_memory(
        cls,
        one_byte_addr,
        two_byte_addr,
        four_byte_addr,
        one_byte_values,
        two_byte_values,
        four_byte_values,
    ):
        counts_bytes = struct.pack(
            "<3H", len(one_byte_addr), len(two_byte_addr), len(four_byte_addr)
        )
        addresses = one_byte_addr + two_byte_addr + four_byte_addr
        addresses_bytes = struct.pack(f"<{len(addresses)}H", *addresses)
        value_bytes = one_byte_values + two_byte_values + four_byte_values

        return cls._create_request_with_command(
            Command.WRITE_RANDOM, counts_bytes + addresses_bytes + value_bytes
        )

    @classmethod
    def _create_request_with_command(cls, command, body_rest=b""):
        return cls._create_with_command(Direction.REQ, Type.COMMAND, command, body_rest)

    @classmethod
    def _create_response_with_command(cls, command, body_rest=b""):
        return cls._create_with_command(Direction.ACK, Type.COMMAND, command, body_rest)

    @classmethod
    def _create_with_command(cls, msg_direction, msg_type, command, body_rest):
        body_bytes = struct.pack("<B", command.value) + body_rest
        return CommandFrame(msg_direction, msg_type.value, body_bytes)

    @classmethod
    def command_frame_to_bytes(cls, command_frame):
        head_bytes = cls._struct_head.pack(
            command_frame.msg_direction.value, command_frame.msg_type
        )
        return head_bytes + command_frame.body_bytes

    @classmethod
    def bytes_to_command_frame(cls, command_frame_bytes):
        if len(command_frame_bytes) < cls.HEAD_LENGTH:
            raise AbusError("Command frame shorter than head")

        head_bytes = command_frame_bytes[: cls.HEAD_LENGTH]
        body_bytes = command_frame_bytes[cls.HEAD_LENGTH :]

        (msg_direction_int, msg_type) = cls._struct_head.unpack(head_bytes)
        msg_direction = Direction(msg_direction_int)

        return CommandFrame(msg_direction, msg_type, body_bytes)
