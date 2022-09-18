import logging


class ConditionalLogger:
    """Constructs message only if it will be logged.

    Good for cases where message formatting is not
    trivial, so time can be saved by skipping unnecessary message formatting.
    """

    def __init__(self, logger):
        self._logger = logger

    def log(self, level, msg, *args, **kwargs):
        if isinstance(msg, str):
            return self._logger.log(level, msg, *args, **kwargs)

        if self._logger.isEnabledFor(level):
            self._logger.log(level, msg(), *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.log(logging.INFO, msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        self.log(logging.DEBUG, msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.log(logging.CRITICAL, msg, *args, **kwargs)


def get_logger(name=None):
    return ConditionalLogger(logging.getLogger(name))
