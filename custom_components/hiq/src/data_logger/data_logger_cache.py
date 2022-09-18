from ..general.async_cache import AsyncCache


class DataLoggerCache:
    def __init__(self, loop):
        self._loop = loop
        self._task_caches = dict()

    def __bool__(self):
        return bool(self._task_caches)

    async def get(self, task_id, crc, default=None):
        try:
            return await self._task_caches[task_id].get(crc, default)
        except KeyError:
            return default

    def set_future(self, task_id, crc):
        task_cache = self._task_caches.get(task_id)

        if task_cache is None:
            task_cache = AsyncCache(self._loop)
            self._task_caches[task_id] = task_cache

        task_cache.set_future(crc)

    def set_future_result(self, task_id, crc, value):
        task_cache = self._task_caches[task_id]

        task_cache.set_future_result(crc, value)

        if not task_cache:
            del self._task_caches[task_id]

    def cancel(self, task_id, crc):
        task_cache = self._task_caches[task_id]

        task_cache.cancel(crc)

        if not task_cache:
            del self._task_caches[task_id]

    def clear(self):
        keys_to_delete = []

        for key in self._task_caches:
            self._task_caches[key].clear()
            keys_to_delete.append(key)

        for key in keys_to_delete:
            del self._task_caches[key]
