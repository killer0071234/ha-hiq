from .data_logger.data_logger import DataLogger
from .data_logger.data_logger_activity_service import DataLoggerActivityService
from .data_logger.data_logger_cache import DataLoggerCache
from .data_logger.data_logger_config_watcher_service import (
    DataLoggerConfigWatcherService,
)
from .general.conditional_logger import get_logger
from .general.logger_names import LoggerNames
from .input_output.abus_stack.abus.abus_transceiver import AbusTransceiver
from .input_output.abus_stack.can_protocol.can_transceiver import CanTransceiver
from .input_output.abus_stack.can_protocol.iex_transceiver import IexTransceiver
from .input_output.abus_stack.router import Router
from .input_output.abus_stack.udp.udp_activity_service import UdpActivityService
from .input_output.abus_stack.udp.udp_transceiver import UdpTransceiver
from .input_output.db.db import Db
from .input_output.db.repository import Repository
from .input_output.scgi.scgi_activity_service import ScgiActivityService
from .input_output.scgi.scgi_server import ScgiServer
from .input_output.tcp.tcp_server import TCPServer
from .services.cpu_intensive_task_runner.cpu_intensive_task_runner import (
    CPUIntensiveTaskRunner,
)
from .services.plc_detection_service.plc_detection_service import PlcDetectionService
from .services.plc_info_service.plc_info_cleaner import PlcInfoCleaner
from .services.plc_info_service.plc_info_service import PlcInfoService
from .services.proxy_service.proxy_activity_service import ProxyActivityService
from .services.proxy_service.proxy_db_synchronizer import ProxyDbSynchronizer
from .services.proxy_service.proxy_service import ProxyService
from .services.push_service.push_activity_service import PushActivityService
from .services.push_service.push_service import PushService
from .services.rw_service.rw_service import RWService
from .services.rw_service.subservices.plc_activity_service.plc_activity_service import (
    PlcActivityService,
)
from .services.rw_service.subservices.plc_comm_service.alc_service.alc_service import (
    AlcService,
)
from .services.rw_service.subservices.plc_comm_service.plc_cache.plc_cache import (
    PlcCache,
)
from .services.rw_service.subservices.plc_comm_service.plc_client_manager.plc_client_manager import (
    PlcClientManager,
)
from .services.rw_service.subservices.plc_comm_service.plc_comm_service import (
    PlcCommService,
)
from .services.status_services.facade.plc_status_service_facade import (
    PlcStatusServiceFacade,
)
from .services.status_services.facade.system_status_service_facade import (
    SystemStatusServiceFacade,
)
from .services.status_services.plc_status_service.plc_status_service import (
    PlcStatusService,
)
from .services.status_services.system_status_service import SystemStatusService
from .startup.system_bootstrap import SystemBootstrap


class IocContainer:
    def __init__(self, config, main_loop, communication_loop, program_file_name):
        """Construct container and set explicit dependencies."""

        self.config = config
        self.main_loop = main_loop
        self.communication_loop = communication_loop
        self.program_file_name = program_file_name

        self._db = None
        self._repository = None
        self._udp_activity_service = None
        self._plc_activity_service = None
        self._scgi_activity_service = None
        self._push_activity_service = None
        self._data_logger_activity_service = None
        self._data_logger_cache = None
        self._plc_info_service = None
        self._static_plc_info_service = None
        self._static_plc_config_watcher_service = None
        self._alc_service = None
        self._system_status_service = None
        self._plc_status_service = None
        self._system_status_service_facade = None
        self._plc_status_service_facade = None
        self._detection_service = None
        self._push_service = None
        self._plc_client_manager = None
        self._plc_cache = None
        self._plc_communication_service = None
        self._rw_service = None
        self._router = None
        self._abus_transceiver = None
        self._udp_transceiver = None
        self._can_transceiver = None
        self._iex_transceiver = None
        self._scgi_server = None
        self._tcp_server = None
        self._data_logger = None
        self._data_logger_config_watcher_service = None
        self._system_bootstrap = None
        self._command_executor = None
        self._cpu_intensive_task_runner = None
        self._proxy_service = None
        self._proxy_activity_service = None
        self._proxy_db_synchronizer = None
        self._plc_info_cleaner = None

    @property
    def cpu_intensive_task_runner(self):
        if self._cpu_intensive_task_runner is None:
            self._cpu_intensive_task_runner = CPUIntensiveTaskRunner()

        return self._cpu_intensive_task_runner

    # region Utility
    @property
    def proxy_service(self):
        if self._proxy_service is None:
            self._proxy_service = ProxyService(
                get_logger(LoggerNames.PROXY.name),
                self.plc_info_service,
                self.plc_client_manager,
                self.main_loop,
                self.communication_loop,
                self.proxy_activity_service,
                self.repository,
                self.proxy_db_synchronizer,
            )

        return self._proxy_service

    @property
    def proxy_activity_service(self):
        if self._proxy_activity_service is None:
            self._proxy_activity_service = ProxyActivityService(
                self.plc_info_service, self.repository
            )

        return self._proxy_activity_service

    # endregion

    # region Database
    @property
    def db(self):
        if self._db is None:
            self._db = Db(get_logger(LoggerNames.DB.name), self.config)

        return self._db

    @property
    def repository(self):
        if self._repository is None:
            self._repository = Repository(
                get_logger(LoggerNames.DB.name),
                self.db,
                self.config,
                self.cpu_intensive_task_runner,
            )

        return self._repository

    # endregion

    # region Activity
    @property
    def udp_activity_service(self):
        if self._udp_activity_service is None:
            self._udp_activity_service = UdpActivityService()

        return self._udp_activity_service

    @property
    def plc_activity_service(self):
        if self._plc_activity_service is None:
            self._plc_activity_service = PlcActivityService()

        return self._plc_activity_service

    @property
    def scgi_activity_service(self):
        if self._scgi_activity_service is None:
            self._scgi_activity_service = ScgiActivityService()

        return self._scgi_activity_service

    @property
    def push_activity_service(self):
        if self._push_activity_service is None:
            self._push_activity_service = PushActivityService()

        return self._push_activity_service

    @property
    def data_logger_activity_service(self):
        if self._data_logger_activity_service is None:
            self._data_logger_activity_service = DataLoggerActivityService()

        return self._data_logger_activity_service

    # endregion

    @property
    def data_logger_cache(self):
        if self._data_logger_cache is None:
            self._data_logger_cache = DataLoggerCache(self.main_loop)

        return self._data_logger_cache

    # region Plc Info
    @property
    def plc_info_service(self):
        if self._plc_info_service is None:
            self._plc_info_service = PlcInfoService(
                get_logger(LoggerNames.PLC_INFO.name),
                self.main_loop,
                self.config,
            )

        return self._plc_info_service

    # endregion

    @property
    def alc_service(self):
        if self._alc_service is None:
            self._alc_service = AlcService(
                get_logger(LoggerNames.ALC.name), self.main_loop, self.config
            )

        return self._alc_service

    # region Status
    @property
    def system_status_service(self):
        if self._system_status_service is None:
            self._system_status_service = SystemStatusService(
                self.config,
                self.plc_info_service,
                self.push_activity_service,
                self.scgi_activity_service,
                self.plc_activity_service,
                self.udp_activity_service,
                self.data_logger_activity_service,
                self.plc_status_service,
                self.proxy_activity_service,
            )
        return self._system_status_service

    @property
    def plc_status_service(self):
        if self._plc_status_service is None:
            self._plc_status_service = PlcStatusService(
                self.plc_info_service, self.plc_activity_service, self.alc_service
            )
        return self._plc_status_service

    @property
    def system_status_service_facade(self):
        if self._system_status_service_facade is None:
            self._system_status_service_facade = SystemStatusServiceFacade(
                self.system_status_service
            )

        return self._system_status_service_facade

    @property
    def plc_status_service_facade(self):
        if self._plc_status_service_facade is None:
            self._plc_status_service_facade = PlcStatusServiceFacade(
                self.plc_status_service
            )

        return self._plc_status_service_facade

    # endregion

    @property
    def detection_service(self):
        if self._detection_service is None:
            self._detection_service = PlcDetectionService(
                get_logger(LoggerNames.PLC_DETECT.name),
                self.plc_info_service,
                self.config,
            )

        return self._detection_service

    @property
    def push_service(self):
        if self._push_service is None:
            self._push_service = PushService(
                get_logger(LoggerNames.PUSH.name),
                self.main_loop,
                self.plc_info_service,
                self.plc_activity_service,
                self.push_activity_service,
                self.config,
            )

        return self._push_service

    @property
    def plc_client_manager(self):
        if self._plc_client_manager is None:
            self._plc_client_manager = PlcClientManager(
                get_logger(LoggerNames.PLC_COMM.name),
                get_logger(LoggerNames.PLC_CLIENT.name),
                self.main_loop,
                self.plc_info_service,
                self.plc_activity_service,
                self.detection_service,
                self.config,
                self.cpu_intensive_task_runner,
            )

        return self._plc_client_manager

    @property
    def plc_cache(self):
        if self.config.cache_config.valid_period == 0:
            self._plc_cache = None
            return self._plc_cache
        if self._plc_cache is None:
            self._plc_cache = PlcCache(self.main_loop, self.config)

        return self._plc_cache

    @property
    def plc_communication_service(self):
        if self._plc_communication_service is None:
            self._plc_communication_service = PlcCommService(
                get_logger(LoggerNames.PLC_COMM.name),
                self.plc_info_service,
                self.alc_service,
                self.plc_activity_service,
                self.plc_client_manager,
                self.plc_cache,
                self.data_logger_cache,
                self.cpu_intensive_task_runner,
                self.config,
            )

        return self._plc_communication_service

    @property
    def rw_service(self):
        if self._rw_service is None:
            self._rw_service = RWService(
                self.system_status_service_facade,
                self.plc_status_service_facade,
                self.plc_communication_service,
                self.cpu_intensive_task_runner,
            )

        return self._rw_service

    @property
    def router(self):
        if self._router is None:
            self._router = Router(
                get_logger(LoggerNames.ABUS.name),
                self.communication_loop,
                self.push_service,
                self.detection_service,
                self.rw_service,
                self.config,
                self.proxy_service,
            )

        return self._router

    @property
    def abus_transceiver(self):
        if self._abus_transceiver is None:
            self._abus_transceiver = AbusTransceiver(
                get_logger(LoggerNames.ABUS.name), self.router, self.config
            )

        return self._abus_transceiver

    @property
    def udp_transceiver(self):
        if self._udp_transceiver is None:
            self._udp_transceiver = UdpTransceiver(
                get_logger(LoggerNames.UDP.name),
                self.main_loop,
                self.communication_loop,
                self.abus_transceiver,
                self.udp_activity_service,
                self.config,
            )

        return self._udp_transceiver

    @property
    def can_transceiver(self):
        if self._can_transceiver is None:
            self._can_transceiver = CanTransceiver(
                self.communication_loop,
                get_logger(LoggerNames.CAN.name),
                self.config,
                self.iex_transceiver,
            )

        return self._can_transceiver

    @property
    def iex_transceiver(self):
        if self._iex_transceiver is None:
            self._iex_transceiver = IexTransceiver(
                get_logger(LoggerNames.CAN.name), self.abus_transceiver
            )

        return self._iex_transceiver

    # region SCGI
    @property
    def scgi_server(self):
        if self._scgi_server is None:
            self._scgi_server = ScgiServer(
                get_logger(LoggerNames.SCGI_SERVER.name),
                self.rw_service,
                self.scgi_activity_service,
                self.config,
            )
        return self._scgi_server

    @property
    def tcp_server(self):
        if self._tcp_server is None:
            self._tcp_server = TCPServer(
                get_logger(LoggerNames.TCP.name),
                self.main_loop,
                self.scgi_server,
                self.config,
            )

        return self._tcp_server

    # endregion

    # region Data Logger
    @property
    def data_logger(self):
        if self._data_logger is None:
            self._data_logger = DataLogger(
                get_logger(LoggerNames.DATA_LOGGER.name),
                self.main_loop,
                self.rw_service,
                self.repository,
                self.data_logger_cache,
                self.data_logger_activity_service,
                self.cpu_intensive_task_runner,
            )

        return self._data_logger

    @property
    def data_logger_config_watcher_service(self):
        if self._data_logger_config_watcher_service is None:
            self._data_logger_config_watcher_service = DataLoggerConfigWatcherService(
                get_logger(), self.main_loop, self.data_logger, self.config
            )
        return self._data_logger_config_watcher_service

    # endregion

    @property
    def system_bootstrap(self):
        if self._system_bootstrap is None:
            self._system_bootstrap = SystemBootstrap(
                get_logger(),
                self.config,
                self.plc_info_service,
                self.plc_client_manager,
                self.db,
                self.alc_service,
                self.udp_transceiver,
                self.can_transceiver,
                self.tcp_server,
                self.data_logger_config_watcher_service,
                self.proxy_service,
                self.plc_info_cleaner,
            )

        return self._system_bootstrap

    @property
    def proxy_db_synchronizer(self):
        if self._proxy_db_synchronizer is None:
            self._proxy_db_synchronizer = ProxyDbSynchronizer(
                get_logger(LoggerNames.PROXY.name),
                self.proxy_activity_service,
                self.config,
            )

        return self._proxy_db_synchronizer

    @property
    def plc_info_cleaner(self):
        if self._plc_info_cleaner is None:
            self._plc_info_cleaner = PlcInfoCleaner(
                get_logger(LoggerNames.PLC_INFO.name),
                self.plc_info_service,
                self.config,
            )

        return self._plc_info_cleaner
