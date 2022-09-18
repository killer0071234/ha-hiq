from dataclasses import dataclass


@dataclass(frozen=True)
class EthConfig:
    @classmethod
    def create(
        cls, enabled, bind_address, port, autodetect_enabled, autodetect_address
    ):

        return EthConfig(
            enabled, bind_address, port, autodetect_enabled, autodetect_address
        )

    enabled: bool
    bind_address: str
    port: int
    autodetect_enabled: bool
    autodetect_address: str

    def props(self):
        return (
            self.enabled,
            self.bind_address,
            self.port,
            self.autodetect_enabled,
            self.autodetect_address,
        )

    @classmethod
    def load(cls, cp, default):
        section = "ETH"

        (
            enabled,
            bind_address,
            port,
            autodetect_enabled,
            autodetect_address,
        ) = default.props()

        eth_bind_addr_from_conf = cp.get(section, "bind_address", fallback=bind_address)

        return cls.create(
            cp.getboolean(section, "enabled", fallback=enabled),
            "0.0.0.0" if eth_bind_addr_from_conf == "" else eth_bind_addr_from_conf,
            cp.getint(section, "port", fallback=port),
            cp.getboolean(section, "autodetect_enabled", fallback=autodetect_enabled),
            cp.get(section, "autodetect_address", fallback=autodetect_address),
        )
