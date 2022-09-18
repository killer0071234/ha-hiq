from ...errors import ScgiServerError


class RWServiceError(ScgiServerError):
    pass


class ScgiCommunicationError(RWServiceError):
    pass


class InvalidTagNameError(ScgiCommunicationError):
    def __init__(self, name: str, *args):
        super().__init__(f'invalid `RWRequest` tag name "{name}"', *args)
        self.name = name
