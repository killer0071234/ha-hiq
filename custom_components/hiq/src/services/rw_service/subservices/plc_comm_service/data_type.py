from enum import Enum


class DataType(Enum):
    NONE = "NONE"
    BIT = "BIT"
    INT = "INT"
    LONG = "LONG"
    REAL = "REAL"


DATA_TYPE_SIZES = {DataType.BIT: 1, DataType.INT: 2, DataType.LONG: 4, DataType.REAL: 4}
