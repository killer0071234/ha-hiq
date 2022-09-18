from ..errors import ScgiServerError


class FileWatcherError(ScgiServerError):
    pass


class TransactionIdGeneratorError(ScgiServerError):
    pass


class UnzipError(ScgiServerError):
    pass


class ExchangerTimeoutError(ScgiServerError):
    pass
