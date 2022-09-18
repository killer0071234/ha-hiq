import struct
from dataclasses import dataclass


@dataclass
class IexCommand:
    instruction: int
    direction: int
    arg: int

    @property
    def is_abus(self):
        return self.arg == 0b010

    @property
    def is_strend(self):
        return self.instruction == 0b1011

    @property
    def is_stream(self):
        return self.instruction == 0b1010

    @property
    def is_response(self):
        return self.direction == 0b0

    def __str__(self):
        return f"INS({self.instruction}) " f"DIR({self.direction}) " f"ARG({self.arg}) "

    @staticmethod
    def iex_command_to_int(iex_command):
        instruction = (iex_command.instruction & 0x0F) << 4
        direction = (iex_command.direction & 0x01) << 3
        arg = iex_command.arg & 0x07
        return instruction | direction | arg

    @staticmethod
    def bytes_to_iex_command(iex_command):
        arg = iex_command & 0x07
        direction = (iex_command >> 3) & 0x01
        instruction = (iex_command >> 4) & 0x0F
        return IexCommand(instruction=instruction, direction=direction, arg=arg)

    @staticmethod
    def create_abus_stream_outgoing():
        return IexCommand(instruction=0b1010, direction=0b1, arg=0b010)

    @staticmethod
    def create_abus_strend_outgoing():
        return IexCommand(instruction=0b1011, direction=0b1, arg=0b010)


@dataclass
class IexFrame:
    command: IexCommand
    address: int
    data: bytes

    _struct_header = struct.Struct(">I")

    @classmethod
    def iex_to_bytes(cls, iex_frame):
        command_int = IexCommand.iex_command_to_int(iex_frame.command)
        header = (command_int << 21) | iex_frame.address
        header_bytes = cls._struct_header.pack(header)

        return header_bytes, iex_frame.data

    @classmethod
    def bytes_to_iex(cls, iex_header_bytes, iex_data_bytes):
        (header,) = cls._struct_header.unpack(iex_header_bytes)
        address = header & 0x1FFFFF
        command = (header >> 21) & 0xFF
        return IexFrame(
            command=IexCommand.bytes_to_iex_command(command),
            address=address,
            data=iex_data_bytes,
        )

    @staticmethod
    def create_abus_stream_out(address, data):
        command = IexCommand.create_abus_stream_outgoing()
        return IexFrame(command=command, address=address, data=data)

    @staticmethod
    def create_abus_strend_out(address, data):
        command = IexCommand.create_abus_strend_outgoing()
        return IexFrame(command=command, address=address, data=data)

    @property
    def is_data_abus_start(self):
        return bytes(self.data[0:2]) == b"\xaa\x55"

    @property
    def is_abus(self):
        return self.command.is_abus

    @property
    def is_stream(self):
        return self.command.is_stream

    @property
    def is_strend(self):
        return self.command.is_strend

    def __str__(self):
        return f"{self.command} {self.address} {self.data.hex()}"
