#!/usr/bin/python
import asyncio
import logging
from datetime import timedelta
from pathlib import Path

from .config.config.abus_config import AbusConfig
from .config.config.cache_config import CacheConfig
from .config.config.can_config import CanConfig
from .config.config.config import Config
from .config.config.data_logger_config import DataLoggerConfig
from .config.config.dbase_config import DbaseConfig
from .config.config.debuglog_config import DebugLogConfig
from .config.config.eth_config import EthConfig
from .config.config.locations_config import LocationsConfig
from .config.config.push_config import PushConfig
from .config.config.relay_config import RelayConfig
from .config.config.scgi_config import ScgiConfig
from .config.config.static_plc_config import StaticPlcConfig
from .config.config.static_plcs_config import StaticPlcsConfig
from .constants import APP_DIR
from .constants import DATA_LOGGER_CONFIG_FILE
from .errors import ScgiServerError
from .general.misc import create_thread_loop
from .ioc_container import IocContainer


async def _setup_scgi_server(comm_loop) -> None:
    try:
        static_plc = StaticPlcConfig(None, "", "192.168.10.202", 8442, 10000)
        config = Config(
            EthConfig(True, "0.0.0.0", 8442, True, "192.168.10.255"),
            PushConfig(False, timedelta(hours=24)),
            CanConfig(False, "can0", "socketcan_native", 100000),
            AbusConfig(timedelta(milliseconds=200), 3, None),
            CacheConfig(
                timedelta(seconds=5), timedelta(seconds=10), timedelta(seconds=30)
            ),
            ScgiConfig("0.0.0.0", 4000, 10, 10, True, False),
            DataLoggerConfig(False),
            DbaseConfig(False, "localhost", 3306, "cybro", "root", "root", 1000000),
            RelayConfig(False, timedelta(minutes=1)),
            LocationsConfig(
                APP_DIR, Path("./log"), Path("./alc"), DATA_LOGGER_CONFIG_FILE
            ),
            DebugLogConfig(True, False, "DEBUG", 1024, 5),
            StaticPlcsConfig([static_plc]),
        )

        container = IocContainer(config, asyncio.get_running_loop(), comm_loop, "")

        await container.system_bootstrap.run()
    except ScgiServerError as exc:
        logging.critical(exc)
        return


if __name__ == "__main__":
    # Create communication loop which will handle abus-related data flow throughout the application.
    # Everything else will be done on main thread (the one this code is currently running on)
    communication_loop, kill_communication_loop = create_thread_loop(
        "CommunicationThread"
    )

    try:
        main_loop = asyncio.get_event_loop()
        main_loop.create_task(_setup_scgi_server(communication_loop))
        main_loop.run_forever()
    # except KeyboardInterrupt as exception:
    #    kill_communication_loop()
    except BaseException as exception:
        print(exception)


def start_server():
    # Create communication loop which will handle abus-related data flow throughout the application.
    # Everything else will be done on main thread (the one this code is currently running on)
    communication_loop, kill_communication_loop = create_thread_loop(
        "CommunicationThread"
    )

    try:
        main_loop = asyncio.get_event_loop()
        main_loop.create_task(_setup_scgi_server(communication_loop))
        main_loop.run_forever()
        return kill_communication_loop
    # except KeyboardInterrupt as exception:
    #    kill_communication_loop()
    except BaseException as exception:
        print(exception)


def stop_server(kill_communication_loop):
    kill_communication_loop()
