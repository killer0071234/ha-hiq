from ...errors import ScgiServerError


class PlcInfoServiceError(ScgiServerError):
    pass


class PlcInfoNotFoundError(PlcInfoServiceError):
    def __init__(self, nad: int, *args):
        super().__init__(f"Plc info for nad {nad} not found", *args)
        self.nad = nad
