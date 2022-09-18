from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class CacheConfig:
    @classmethod
    def create(cls, request_period_s, valid_period_s, cleanup_period_s):
        return CacheConfig(
            timedelta(seconds=request_period_s),
            timedelta(seconds=valid_period_s),
            timedelta(seconds=cleanup_period_s),
        )

    request_period: timedelta
    valid_period: timedelta
    cleanup_period_s: timedelta

    def props(self):
        return (
            self.request_period.total_seconds(),
            self.valid_period.total_seconds(),
            self.cleanup_period_s.total_seconds(),
        )

    @classmethod
    def load(cls, cp, default):
        section = "CACHE"

        request_period_s, valid_period_s, cleanup_period_s = default.props()

        return cls.create(
            cp.getint(section, "request_period_s", fallback=request_period_s),
            cp.getint(section, "valid_period_s", fallback=valid_period_s),
            cp.getint(section, "cleanup_period_s", fallback=cleanup_period_s),
        )
