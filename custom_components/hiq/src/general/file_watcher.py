import os
import sys
from pathlib import Path

from rx.operators import debounce
from rx.operators import distinct_until_changed
from rx.operators import observe_on
from rx.scheduler.eventloop import AsyncIOThreadSafeScheduler
from rx.subject import BehaviorSubject
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..general.errors import FileWatcherError


class FileWatcher:
    """Watches specified file for changes.

    On each change emits timestamp and file path as a tuple.
    """

    DEBOUNCE_S = 0.3
    CONFIG_PATH = Path.cwd().joinpath(Path("../config.ini")).resolve().as_posix()
    configTimestamp = {CONFIG_PATH: 0.0}

    class EventHandler(FileSystemEventHandler):
        def __init__(self, file, _timestamp, _log):
            self._file = file
            self._timestamp = _timestamp
            self._log = _log
            self._config_timestamp = FileWatcher.configTimestamp

        def on_any_event(self, event):
            if event.is_directory or "~" in event.src_path:
                return
            super().on_any_event(event)
            # FileWatcher.update_subject_with_file(self._timestamp, self._file)
            FileWatcher.update_subject_with_file(
                self._timestamp, Path(event.src_path.replace("\\", "/")), self._log
            )

    def __init__(self, loop, config, log):
        self._loop = loop
        self._file = config.locations_config.data_logger_config_file

        self._timestamp = None
        self._observer = None
        self._log = log
        self._config = config

    @property
    def running(self):
        return self._timestamp is not None

    def start(self):
        if self.running:
            raise FileWatcherError("Can't start cause it's already running")

        self._timestamp = BehaviorSubject((None, None))
        self._observer = Observer()

        segments = self._file.as_posix().split("/")
        directory = Path("/".join(segments[:-1]))
        self._observer.schedule(
            self.EventHandler(self._file, self._timestamp, self._log),
            directory.as_posix(),
        )

        self._observer.start()

        FileWatcher.update_subject_with_file(self._timestamp, self._file, self._log)

        if self._config.data_logger_config.datalogger_enabled:
            return self._timestamp.pipe(
                distinct_until_changed(
                    comparer=lambda first, second: first[1] == second[1]
                ),
                debounce(self.DEBOUNCE_S),
                observe_on(AsyncIOThreadSafeScheduler(self._loop)),
            )

    def stop(self):
        if not self.running:
            raise FileWatcherError("Can't stop cause it's not running")

        self._timestamp.on_completed()
        self._observer.stop()
        self._timestamp = None
        self._observer = None

    @classmethod
    def update_subject_with_file(cls, subject, file, log):
        # Restart if config.ini changed
        config_file_mtime = os.stat(FileWatcher.CONFIG_PATH).st_mtime
        if (
            FileWatcher.configTimestamp[FileWatcher.CONFIG_PATH] != config_file_mtime
            and FileWatcher.configTimestamp[FileWatcher.CONFIG_PATH] != 0.0
        ):
            FileWatcher.restart(log)
        FileWatcher.configTimestamp[FileWatcher.CONFIG_PATH] = config_file_mtime

        old_timestamp = subject.value
        file_path = file.as_posix()

        new_timestamp = None
        try:
            if os.path.isfile(file_path):
                new_timestamp = os.stat(file.as_posix()).st_mtime
        except FileNotFoundError:
            new_timestamp = None

        if old_timestamp != new_timestamp:  # !!!
            result = (None if new_timestamp is None else file, new_timestamp)
            subject.on_next(result)

    @staticmethod
    def restart(log):
        log.info(sys.argv[0] + " " + sys.executable)
        args = sys.argv[:]
        log.info("Re-spawning %s" % " ".join(args))
        args.insert(0, sys.executable)
        if sys.platform == "win32":
            args = ['"%s"' % arg for arg in args]

        os.chdir(os.getcwd())
        os.execv(sys.executable, args)
