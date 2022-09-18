from datetime import timedelta
from pathlib import Path

from ...constants import APP_DIR
from ...constants import DATA_LOGGER_CONFIG_FILE
from ..config.abus_config import AbusConfig
from ..config.cache_config import CacheConfig
from ..config.can_config import CanConfig
from ..config.config import Config
from ..config.data_logger_config import DataLoggerConfig
from ..config.dbase_config import DbaseConfig
from ..config.debuglog_config import DebugLogConfig
from ..config.eth_config import EthConfig
from ..config.locations_config import LocationsConfig
from ..config.push_config import PushConfig
from ..config.relay_config import RelayConfig
from ..config.scgi_config import ScgiConfig
from ..config.static_plcs_config import StaticPlcsConfig

_DEFAULT_ETH_CONFIG = EthConfig(True, "0.0.0.0", 8442, True, "192.168.1.255")

_DEFAULT_PUSH_CONFIG = PushConfig(False, timedelta(hours=24))

_DEFAULT_LOCATIONS_CONFIG = LocationsConfig(
    APP_DIR, Path("./log"), Path("./alc"), DATA_LOGGER_CONFIG_FILE
)

_DEFAULT_CAN_CONFIG = CanConfig(False, "can0", "socketcan_native", 100000)

_DEFAULT_ABUS_CONFIG = AbusConfig(timedelta(milliseconds=200), 3, None)

_DEFAULT_SCGI_CONFIG = ScgiConfig("0.0.0.0", 4000, 10, 10, True, False)

_DEFAULT_CACHE_CONFIG = CacheConfig(
    timedelta(seconds=0), timedelta(seconds=0), timedelta(seconds=0)
)

_DEFAULT_DATA_LOGGER_CONFIG = DataLoggerConfig(True)

_DEFAULT_RELAY_CONFIG = RelayConfig(True, timedelta(minutes=1))

_DEFAULT_DBASE_CONFIG = DbaseConfig(
    True, "localhost", 3306, "cybro", "root", "root", 1000000
)

_DEFAULT_DEBUGLOG_CONFIG = DebugLogConfig(True, True, "DEBUG", 1024, 5)

_DEFAULT_PLCS_CONFIG = StaticPlcsConfig([])


def create_default_config():
    return Config(
        _DEFAULT_ETH_CONFIG,
        _DEFAULT_PUSH_CONFIG,
        _DEFAULT_CAN_CONFIG,
        _DEFAULT_ABUS_CONFIG,
        _DEFAULT_CACHE_CONFIG,
        _DEFAULT_SCGI_CONFIG,
        _DEFAULT_DATA_LOGGER_CONFIG,
        _DEFAULT_DBASE_CONFIG,
        _DEFAULT_RELAY_CONFIG,
        _DEFAULT_LOCATIONS_CONFIG,
        _DEFAULT_DEBUGLOG_CONFIG,
        _DEFAULT_PLCS_CONFIG,
    )
