from dataclasses import dataclass

from ......services.rw_service.subservices.plc_comm_service.data_type import DataType


@dataclass(frozen=True)
class VarInfo:
    id: int
    name: str
    is_array: bool
    array_size: int
    address: int
    offset: int
    size: int
    scope: str
    data_type: DataType
    description: str

    def __str__(self) -> str:
        return (
            f"{self.name}: id={self.id}, is_array={self.is_array}, "
            f"address={self.address}, offset={self.offset}, size={self.size}, "
            f"scope={self.scope}, data_type={self.data_type.name}, "
            f"description={self.description}"
        )
