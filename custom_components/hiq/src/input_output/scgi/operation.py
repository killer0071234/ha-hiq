from dataclasses import dataclass
from email.parser import BytesParser
from typing import Optional

from ...input_output.scgi.errors import ScgiError


@dataclass(frozen=True)
class Operation:
    key: str
    value: Optional[str] = None

    def __str__(self) -> str:
        if self.is_read:
            return self.key
        else:
            return f"{self.key}={self.value}"

    @property
    def is_read(self) -> bool:
        return self.value is None

    @property
    def is_write(self) -> bool:
        return not self.is_read


class OperationUtil:
    """
    Extracts operation objects from binary data (HTTP or simple binary format)
    """

    class Keys:
        REQUEST_URI = "REQUEST_URI"
        QUERY_STRING = "QUERY_STRING"
        REMOTE_ADDR = "REMOTE_ADDR"
        REMOTE_PORT = "REMOTE_PORT"

    @classmethod
    def bytes_to_operations(cls, operations_bytes):
        parsed = cls._parse_http_request(operations_bytes)

        query_string = parsed[cls.Keys.QUERY_STRING]

        return cls._extract_operations_from_query_string(query_string)

    @classmethod
    def _parse_http_request(cls, data):
        try:
            request_line, headers = data.split(b"\r\n", 1)
            (method, uri, protocol) = request_line.split()
            path, query_string = uri.split(b"?")
        except (TypeError, ValueError) as e:
            raise ScgiError(f"Http request error\n{data}") from e

        parsed_headers = BytesParser().parsebytes(headers)

        remote_addr_bytes = parsed_headers["X-Forwarded-For:"]
        remote_addr = "" if remote_addr_bytes is None else remote_addr_bytes.encode()

        return {
            cls.Keys.REQUEST_URI: uri.decode(),
            cls.Keys.QUERY_STRING: query_string.decode(),
            cls.Keys.REMOTE_ADDR: remote_addr,
            cls.Keys.REMOTE_PORT: "0",
        }

    @classmethod
    def _parse_tcp_request(cls, data):
        items = data.split(b"\0")[:-1]

        if len(items) % 2 == 0:
            raise ScgiError(f"Tcp request error\n{data}")

        result = {}

        for i in range(0, len(items), 2):
            key = items[i].decode()
            value = items[i + 1].decode()
            result[key] = value

        return result

    @classmethod
    def _extract_operations_from_query_string(cls, query_string):
        read_operations_by_key = {}
        write_operations = []

        for entry_str in query_string.split("&"):
            entry_members = entry_str.split("=")

            key = entry_members[0]
            try:
                write_operations.append(Operation(key, entry_members[1]))
                read_operations_by_key[key] = Operation(key)
            except IndexError:
                read_operations_by_key[key] = Operation(key)

        return read_operations_by_key.values(), write_operations
