from ..errors import ScgiServerError


class DataLoggerError(ScgiServerError):
    pass


class UnexpectedValue(DataLoggerError):
    def __init__(self, value_str, *args):
        super().__init__(f'Unexpected value "{value_str}"', *args)
        self.value_str = value_str
