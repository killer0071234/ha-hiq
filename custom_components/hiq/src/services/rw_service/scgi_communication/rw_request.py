import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ....services.rw_service.errors import InvalidTagNameError
from ....services.rw_service.scgi_communication.operation_type import OperationType


@dataclass(frozen=True)
class RWRequest:
    @classmethod
    def create(cls, name, value=None, idx=None):
        if len(name) == 0:
            raise InvalidTagNameError(name)

        operation_type = OperationType.READ if value is None else OperationType.WRITE
        (target, tag_name, nad) = cls._determine_target_tag_name_and_nad(name)

        return cls(name, tag_name, value, operation_type, target, nad, idx)

    class Target(Enum):
        SYSTEM = (0,)
        PLC_SYSTEM = (1,)
        PLC = 2

    name: str
    tag_name: str
    value: str
    type: OperationType
    target: Target
    nad: int
    idx: Optional[int]

    @classmethod
    def _determine_target_tag_name_and_nad(cls, name):
        (plc_name, separator, rest_of_name) = name.partition(".")

        if plc_name == "sys":
            return cls.Target.SYSTEM, rest_of_name, None

        match = re.search(r"^c(\d+)$", plc_name)

        if match is not None:
            try:
                nad = int(match[1])
            except ValueError:
                raise InvalidTagNameError(name)

            if rest_of_name.startswith("sys"):
                return cls.Target.PLC_SYSTEM, rest_of_name.partition(".")[-1], nad
            else:
                return cls.Target.PLC, rest_of_name, nad
        else:
            raise InvalidTagNameError(name)
