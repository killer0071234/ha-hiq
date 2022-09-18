import asyncio


class AsyncCache:
    def __init__(self, loop):
        self._loop = loop
        self._futures = {}

    def __bool__(self):
        return bool(self._futures)

    async def get(self, key, default=None):
        try:
            res = await self._futures[key]

            return res
        except (KeyError, asyncio.CancelledError):
            return default

    def set_future(self, key):
        self._futures[key] = self._loop.create_future()

    def set_future_result(self, key, value):
        self._futures[key].set_result(value)

    def cancel(self, key):
        self._futures[key].cancel()
        del self._futures[key]

    def clear(self):
        for key in self._futures:
            self.cancel(key)
