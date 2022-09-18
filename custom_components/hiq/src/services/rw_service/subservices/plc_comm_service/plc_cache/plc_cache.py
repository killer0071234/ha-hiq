from rx import timer
from rx.scheduler.eventloop import AsyncIOScheduler

from ......services.rw_service.subservices.plc_comm_service.plc_cache.single_plc_cache import (
    SinglePlcCache,
)


class PlcCache:
    def __init__(self, loop, config):
        self._loop = loop
        self._cache_config = config.cache_config
        self._plc_caches = {}

        cleanup_period_s = self._cache_config.cleanup_period_s.total_seconds()

        if cleanup_period_s != 0:
            timer(cleanup_period_s, cleanup_period_s, AsyncIOScheduler(loop)).subscribe(
                lambda _: self._cleanup()
            )

    def __getitem__(self, nad):
        try:
            return self._plc_caches[nad]
        except KeyError:
            result = SinglePlcCache(
                self._loop,
                self._cache_config.request_period,
                self._cache_config.valid_period,
            )
            self._plc_caches[nad] = result
            return result

    def _cleanup(self):
        for nad in self._plc_caches:
            self._plc_caches[nad].cleanup()
