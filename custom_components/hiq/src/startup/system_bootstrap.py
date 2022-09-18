class SystemBootstrap:
    """Starts and wires up all important parts of the system"""

    def __init__(
        self,
        log,
        config,
        plc_info_service,
        plc_client_manager,
        db,
        alc_service,
        udp_transceiver,
        can_transceiver,
        tcp_server,
        data_logger_config_watcher_service,
        proxy_service,
        plc_info_cleaner,
    ):
        self._log = log
        self._config = config
        self._plc_info_service = plc_info_service
        self._plc_client_manager = plc_client_manager
        self._db = db
        self._alc_service = alc_service
        self._udp_transceiver = udp_transceiver
        self._can_transceiver = can_transceiver
        self._tcp_server = tcp_server
        self._data_logger_config_watcher_service = data_logger_config_watcher_service
        self._proxy_service = proxy_service
        self._plc_info_cleaner = plc_info_cleaner

    async def run(self) -> None:
        self._plc_info_service.set_plc_client_manager(self._plc_client_manager)
        self._plc_info_service.load_static_plc_infos()

        if (
            self._config.relay_config.relay_enabled
            or self._config.data_logger_config.datalogger_enabled
        ):
            self._log.info("Initializing database")
            await self._db.start()

        self._log.info("Initializing alc service with alc files")
        await self._alc_service.initialize_with_alc_files()

        if self._config.eth_config.enabled:
            self._log.info("Initializing UDP communication")
            await self._udp_transceiver.start()
        else:
            self._log.info("Skipped UDP initialization")

        self._log.info("Initializing TCP communication")
        await self._tcp_server.start()

        if self._config.can_config.enabled:
            self._log.info("Initializing CAN communication")
            self._can_transceiver.start()
        else:
            self._log.info("Skipped CAN initialization")

        # if self._config.data_logger_config.datalogger_enabled
        self._data_logger_config_watcher_service.start()

        if self._config.relay_config.relay_enabled:
            self._proxy_service.start()

        self._plc_info_cleaner.start()
