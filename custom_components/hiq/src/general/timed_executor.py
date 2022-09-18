import asyncio
from abc import ABC
from abc import abstractmethod
from datetime import datetime


class Timer(ABC):
    def __init__(self, duration_s):
        self._duration_s = duration_s

    def start(self):
        asyncio.get_running_loop().create_task(self._execute_wait_and_repeat())

    async def _execute_wait_and_repeat(self):
        start_time = datetime.now()
        await self.execute()
        end_time = datetime.now()
        duration = end_time - start_time
        delay = self._duration_s - duration.total_seconds()
        await asyncio.sleep(delay)
        asyncio.get_running_loop().create_task(self._execute_wait_and_repeat())

    @abstractmethod
    async def execute(self):
        pass
