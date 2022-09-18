from enum import auto
from enum import Enum


class LoggerNames(Enum):
    TCP = auto()
    UDP = auto()
    CAN = auto()
    PUSH = auto()
    ABUS = auto()
    PLC_INFO = auto()
    PLC_CLIENT = auto()
    PLC_COMM = auto()
    ALC = auto()
    SCGI_SERVER = (auto(),)
    PLC_DETECT = (auto(),)
    DB = auto()
    DATA_LOGGER = auto()
    PROXY = auto()
