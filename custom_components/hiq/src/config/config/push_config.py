from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class PushConfig:
    @classmethod
    def create(cls, enabled, timeout_h):
        return cls(enabled, timedelta(hours=timeout_h))

    enabled: bool
    timeout_h: timedelta

    def props(self):
        return self.enabled, self.timeout_h.total_seconds() * 60 * 60

    @classmethod
    def load(cls, cp, default):
        section = "PUSH"

        enabled, timeout_h = default.props()

        return cls.create(
            cp.getboolean(section, "enabled", fallback=enabled),
            cp.getint(section, "timeout_h", fallback=timeout_h),
        )
