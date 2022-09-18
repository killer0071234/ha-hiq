import logging.handlers
import os
import sys

from ..constants import LOG_TO_STD_OUT


def init_logging(config):
    handlers = []

    log_config = config.debuglog_config

    if log_config.enabled:

        if log_config.log_to_file:
            handlers.append(
                _create_file_handler(
                    config.debuglog_config.verbose_level,
                    config.locations_config.log_dir,
                    "scgi",
                    config.debuglog_config.max_log_file_size_kb,
                    config.debuglog_config.max_log_backup_count,
                )
            )

        if LOG_TO_STD_OUT:
            handlers.append(logging.StreamHandler(sys.stdout))

        logging.basicConfig(
            level=log_config.verbose_level,
            format="%(asctime)s |"
            " %(threadName)-10.10s |"
            " %(levelname)-5.5s |"
            " %(name)-18.18s |"
            " %(message)s",
            datefmt="%m.%d.%Y %H:%M:%S",
            handlers=handlers,
        )


def _create_file_handler(level, log_dir, filename, max_size_kb, backup_count):
    file = log_dir.joinpath(f"{filename}.log")

    if not os.path.isdir(log_dir):
        os.makedirs(log_dir, mode=0o755, exist_ok=False)

    result = logging.handlers.RotatingFileHandler(
        str(file), maxBytes=max_size_kb * 1000, backupCount=backup_count
    )
    result.setLevel(level)
    return result
