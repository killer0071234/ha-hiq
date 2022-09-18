from dataclasses import dataclass


@dataclass(frozen=True)
class DataLoggerConfig:
    datalogger_enabled: bool

    def props(self):
        return self.datalogger_enabled

    @classmethod
    def load(cls, cp, default):
        section = "DATALOGGER"

        datalogger_enabled = default.props()

        return cls(
            cp.getboolean(section, "enabled", fallback=datalogger_enabled),
        )
