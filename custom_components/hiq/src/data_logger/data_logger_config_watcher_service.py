from rx import create
from rx import just
from rx.disposable import Disposable
from rx.operators import do_action
from rx.operators import filter
from rx.operators import flat_map
from rx.operators import map

from ..config.data_logger_config.data_logger_config_xml_parser import (
    parse_data_logger_xml,
)
from ..config.errors import DataLoggerXmlParserError
from ..general.file_watcher import FileWatcher
from ..general.misc import create_task_callback


class DataLoggerConfigWatcherService:
    def __init__(self, log, loop, data_logger, config):
        self._log = log
        self._loop = loop
        self._data_logger = data_logger
        self._config_file = config.locations_config.data_logger_config_file
        self._file_watcher = FileWatcher(loop, config, self._log)
        self._config = config

    def start(self):

        if self._config.data_logger_config.datalogger_enabled:
            self._log.info(
                lambda: f'Watching data logger config file "{self._config_file.as_posix()}"'
            )

            def log(data_logger_config) -> None:
                if data_logger_config is not None:
                    self._log.info("Data logger config file reloaded")
                else:
                    self._log.warning("Data logger config file gone")

            self._file_watcher.start().pipe(
                map(lambda file_and_timestamp: file_and_timestamp[0]),  # !!!
                flat_map(
                    lambda file: just(None)
                    if file is None
                    else self._read_data_logger_config_observable()
                ),
                filter(lambda config: config is not None),
                do_action(log),
            ).subscribe(lambda config: self._data_logger.on_data_logger_config(config))
        else:
            self._log.info(lambda: "Watching config.ini file")
            self._file_watcher.start()

    def _read_data_logger_config_observable(self):
        def subscription(observer, _):
            async def task():
                observer.on_next(await self._read_data_logger_config())
                observer.on_completed()

            self._loop.create_task(task()).add_done_callback(
                create_task_callback(self._log)
            )

            return Disposable()

        return create(subscription)

    async def _read_data_logger_config(self):
        text = await self._load_config_text()

        if text is None:
            self._log.warning("No data logger config xml.")
            return

        try:
            return parse_data_logger_xml(text)
        except DataLoggerXmlParserError as e:
            self._log.error("Can't parse data logger config xml.", exc_info=e)

    async def _load_config_text(self):
        blocking_task = self._load_config_text_blocking
        return await self._loop.run_in_executor(None, blocking_task)

    def _load_config_text_blocking(self):
        try:
            with self._config_file.open("r", encoding="utf-8") as f:
                return f.read()
        except OSError as e:
            self._log.error(
                lambda: f'Can\'t load file "{self._config_file.as_posix()}"', exc_info=e
            )
