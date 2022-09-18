from configparser import ParsingError
from dataclasses import dataclass

from ..config.abus_config import AbusConfig
from ..config.cache_config import CacheConfig
from ..config.can_config import CanConfig
from ..config.data_logger_config import DataLoggerConfig
from ..config.dbase_config import DbaseConfig
from ..config.debuglog_config import DebugLogConfig
from ..config.eth_config import EthConfig
from ..config.locations_config import LocationsConfig
from ..config.push_config import PushConfig
from ..config.relay_config import RelayConfig
from ..config.scgi_config import ScgiConfig
from ..config.static_plcs_config import StaticPlcsConfig
from ..errors import ConfigError


@dataclass(frozen=True)
class Config:
    eth_config: EthConfig
    push_config: PushConfig
    can_config: CanConfig
    abus_config: AbusConfig
    cache_config: CacheConfig
    scgi_config: ScgiConfig
    data_logger_config: DataLoggerConfig
    dbase_config: DbaseConfig
    relay_config: RelayConfig
    locations_config: LocationsConfig
    debuglog_config: DebugLogConfig
    static_plcs_config: StaticPlcsConfig

    def props(self):
        return (
            self.eth_config,
            self.push_config,
            self.can_config,
            self.abus_config,
            self.cache_config,
            self.scgi_config,
            self.data_logger_config,
            self.dbase_config,
            self.relay_config,
            self.locations_config,
            self.debuglog_config,
            self.static_plcs_config,
        )

    @classmethod
    def load(cls, cp, default):
        (
            eth_config,
            push_config,
            can_config,
            abus_config,
            cache_config,
            scgi_config,
            data_logger_config,
            dbase_config,
            relay_config,
            locations_config,
            debuglog_config,
            static_plcs_config,
        ) = default.props()

        try:
            return cls(
                EthConfig.load(cp, eth_config),
                PushConfig.load(cp, push_config),
                CanConfig.load(cp, can_config),
                AbusConfig.load(cp, abus_config),
                CacheConfig.load(cp, cache_config),
                ScgiConfig.load(cp, scgi_config),
                DataLoggerConfig.load(cp, data_logger_config),
                DbaseConfig.load(cp, dbase_config),
                RelayConfig.load(cp, relay_config),
                LocationsConfig.load(cp, locations_config),
                DebugLogConfig.load(cp, debuglog_config),
                StaticPlcsConfig.load(cp),
            )
        except ParsingError as e:
            raise ConfigError("Can't read config file") from e
