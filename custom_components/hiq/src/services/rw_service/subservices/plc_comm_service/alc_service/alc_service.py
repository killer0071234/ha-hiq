import functools
import os
import re

from ......general.misc import create_task_callback
from ......services.rw_service.subservices.plc_comm_service.alc_service.alc_parser import (
    AlcParser,
)


class AlcService:
    CRC_FILENAME_REGEX = re.compile("^crc-(\\d+).alc")
    ENCODING = "latin-1"

    def __init__(self, log, loop, config):
        self._log = log
        self._loop = loop
        self._alc_dir = config.locations_config.alc_dir
        self._crc_to_alc = {}

    async def initialize_with_alc_files(self):
        async for crc, alc in self._read_alc_files():
            self._crc_to_alc[crc] = alc

    async def _read_alc_files(self):
        if not self._alc_dir.exists():
            os.makedirs(self._alc_dir.resolve(), mode=0o755, exist_ok=False)
        else:
            for f in self._alc_dir.iterdir():
                if not f.is_file():
                    continue

                crc = self._filename_to_crc(f.name)
                if crc is None:
                    self._log.error(lambda: f'Invalid alc filename "{f.name}"')
                    continue

                alc = await self._load_alc(f)
                if alc is None:
                    continue

                yield (crc, alc)

    def set_alc_text(self, alc_text, crc):
        self._loop.create_task(self._save_alc_text(alc_text, crc)).add_done_callback(
            create_task_callback(self._log)
        )

        self[crc] = AlcParser.parse(alc_text)

    def __getitem__(self, crc):
        return self._crc_to_alc[crc]

    def __setitem__(self, crc, alc):
        self._log.info(f"Add alc with crc={crc}")
        self._crc_to_alc[crc] = alc

    async def _load_alc(self, path):
        alc_text = await self._load_alc_text(path)
        if alc_text is None:
            return None
        return AlcParser.parse(alc_text)

    async def _save_alc_text(self, alc_text, crc):
        blocking_task = functools.partial(self._save_alc_text_blocking, alc_text, crc)
        return await self._loop.run_in_executor(None, blocking_task)

    async def load_alc_text_for_crc(self, crc):
        path = self._alc_dir.joinpath(self._crc_to_filename(crc))
        return await self._load_alc_text(path)

    async def _load_alc_text(self, path):
        blocking_task = functools.partial(self._load_alc_text_blocking, path)
        return await self._loop.run_in_executor(None, blocking_task)

    def _save_alc_text_blocking(self, alc_text: str, crc: int) -> None:
        path = self._alc_dir.joinpath(self._crc_to_filename(crc))

        try:
            with path.open("w", encoding=self.ENCODING) as f:
                f.write(alc_text)
                f.flush()
        except OSError as e:
            self._log.error(lambda: f'Can\'t save alc file "{path}"', exc_info=e)

    def _load_alc_text_blocking(self, alc_path):
        try:
            with alc_path.open("r", encoding=self.ENCODING) as f:
                return f.read()
        except OSError as e:
            self._log.error(lambda: f'Can\'t load alc file "{alc_path}"', exc_info=e)

    @classmethod
    def _crc_to_filename(cls, crc: int) -> str:
        return f"crc-{crc}.alc"

    @classmethod
    def _filename_to_crc(cls, filename):
        match = cls.CRC_FILENAME_REGEX.match(filename)
        if match is None:
            return None

        crc_str = match.group(1)

        try:
            return int(crc_str)
        except ValueError:
            return None
