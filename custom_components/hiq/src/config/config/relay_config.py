from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class RelayConfig:
    @classmethod
    def create(cls, relay_enabled, db_sync_timeout_min):
        return cls(relay_enabled, timedelta(seconds=db_sync_timeout_min * 60))

    relay_enabled: bool
    db_sync_timeout_min: timedelta

    def props(self):
        return self.relay_enabled, self.db_sync_timeout_min.total_seconds() * 60

    @classmethod
    def load(cls, cp, default):
        section = "RELAY"

        enabled, db_sync_timeout_min = default.props()

        return cls.create(
            cp.getboolean(section, "enabled", fallback=enabled),
            cp.getint(section, "db_sync_timeout_min", fallback=db_sync_timeout_min),
        )
