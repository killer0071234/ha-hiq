import asyncio


class CPUIntensiveTaskRunner:
    def __init__(self):
        # Experimental - uncomment to turn on multiprocessing
        # self._process_pool = ProcessPoolExecutor()
        pass

    async def run(self, function, *args):
        loop = asyncio.get_running_loop()  # noqa: F841
        return function(*args)
        # Experimental - uncomment to turn on multiprocessing
        # return await loop.run_in_executor(self._process_pool, function, *args)
