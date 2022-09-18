import asyncio

import aiomysql
from aiomysql import DatabaseError

from ...errors import ScgiServerError


class Db:
    def __init__(self, log, config):
        self._log = log
        self._config = config.dbase_config
        self._pool = None

    async def start(self):
        try:
            self._pool = await aiomysql.create_pool(
                host=self._config.host,
                port=self._config.port,
                user=self._config.user,
                password=self._config.password,
                db=self._config.name,
                loop=asyncio.get_running_loop(),
                autocommit=True,
            )

            async with self._pool.acquire() as conn:
                self._log.info(
                    lambda: f"Connected to database {conn.host}:{conn.port}/{conn.db}"
                )
        except DatabaseError as e:
            self._log.critical("Couldn't connect to database", exc_info=e)
            raise ScgiServerError() from e

    async def execute_query(self, query):
        self._log.debug(lambda: f"{query[:100]}...")

        async with self._pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query)
                result = await cursor.fetchall()
                return result
