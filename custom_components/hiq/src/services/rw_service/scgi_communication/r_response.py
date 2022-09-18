from dataclasses import dataclass
from enum import Enum
from typing import List
from typing import Union


@dataclass
class RResponse:
    @classmethod
    def create(
        cls,
        name,
        tag_name,
        value="?",
        description="",
        valid=True,
        code=None,
        cached=False,
    ):
        if code is None:
            code = cls.Code.NO_ERROR
        return cls(name, tag_name, value, description, valid, code, cached)

    class Code(Enum):
        NO_ERROR = 0
        TIMEOUT = 1
        UNKNOWN = 2
        DEVICE_NOT_FOUND = 3
        PLC_HEAD_ERROR = 4
        NO_ALC_ERROR = 5

    name: str
    tag_name: str
    value: Union[str, List[str]]
    description: str
    valid: bool
    code: Code
    cached: bool

    def __str__(self):
        result = f"{self.name}={self.value}"

        if self.code != self.Code.NO_ERROR:
            result += f" {self.code.name}"

        if self.description != "":
            result += f' "{self.description}"'

        return result
