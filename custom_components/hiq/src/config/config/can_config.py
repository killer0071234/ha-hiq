from dataclasses import dataclass


@dataclass(frozen=True)
class CanConfig:
    @classmethod
    def create(cls, enabled, channel, interface, bitrate):
        return cls(enabled, channel, interface, bitrate)

    enabled: bool
    channel: str
    interface: str
    bitrate: int

    def props(self):
        return self.enabled, self.channel, self.interface, self.bitrate

    @classmethod
    def load(cls, cp, default):
        section = "CAN"

        enabled, channel, interface, bitrate = default.props()

        return cls.create(
            cp.getboolean(section, "enabled", fallback=enabled),
            cp.get(section, "channel", fallback=channel),
            cp.get(section, "interface", fallback=interface),
            cp.getint(section, "bitrate", fallback=bitrate),
        )
