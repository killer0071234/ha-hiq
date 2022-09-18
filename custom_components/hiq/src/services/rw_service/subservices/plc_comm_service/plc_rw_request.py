from dataclasses import dataclass
from typing import Optional
from typing import Union

from .....services.rw_service.subservices.plc_comm_service.data_type import DataType


@dataclass(frozen=True)
class AlcData:
    addr: int
    size: int
    data_type: DataType
    description: str


@dataclass(frozen=True)
class PlcRWRequest:
    @classmethod
    def create(cls, name, value_str, var_name, alc_data=None, idx=None):
        if value_str is None or alc_data is None:
            value = None
        else:
            if alc_data.data_type == DataType.REAL:
                value = float(value_str)
            else:
                value = int(float(value_str))

        return cls(name, value, var_name, alc_data, idx)

    name: str
    value: Optional[Union[int, float]]
    var_name: str
    alc_data: Optional[AlcData]
    idx: Optional[int]

    @property
    def is_valid(self):
        return self.alc_data is not None

    def __str__(self):
        index_str = "" if self.idx is None else f"[{self.idx}]"
        prefix = (
            self.var_name
            if self.value is None
            else f"{self.var_name}{index_str}={self.value}"
        )
        suffix = str(self.alc_data) if self.is_valid else "INVALID"
        return f"{prefix} {suffix}"
