from ..errors import ScgiServerError


class ConfigError(ScgiServerError):
    pass


class InvalidPlcName(ConfigError):
    def __init__(self, name: str, *args):
        super().__init__(f'invalid plc config name "{name}"', *args)
        self.name = name


class InvalidPassword(ConfigError):
    def __init__(self, password: str, *args):
        super().__init__(f'invalid password "{password}"', *args)
        self.password = password


class DataLoggerXmlParserError(ConfigError):
    def __init__(self, *args):
        super().__init__("Invalid data logger xml", *args)


class UnexpectedTagError(DataLoggerXmlParserError):
    def __init__(self, tag: str, *args):
        super().__init__(f"Unexpected tag {tag}", *args)


class MissingTagError(DataLoggerXmlParserError):
    def __init__(self, tag: str, *args):
        super().__init__(f"Missing tag {tag}", *args)
