from ...general.timed_executor import Timer


class ProxyDbSynchronizer(Timer):
    def __init__(self, log, proxy_activity_service, config):
        super().__init__(config.relay_config.db_sync_timeout_min.total_seconds())
        self._log = log
        self._proxy_activity_service = proxy_activity_service

    async def execute(self):
        self._log.debug("Synchronizing with database")
        await self._proxy_activity_service.update_from_db()
