from dataclasses import dataclass


@dataclass(frozen=True)
class ScgiConfig:
    scgi_bind_address: str
    scgi_port: int
    request_timeout_s: int
    config_check_period_s: int
    reply_with_descriptions: bool
    tls_enabled: bool

    def props(self):
        return (
            self.scgi_bind_address,
            self.scgi_port,
            self.request_timeout_s,
            self.config_check_period_s,
            self.reply_with_descriptions,
            self.tls_enabled,
        )

    @classmethod
    def load(cls, cp, default):
        section = "SCGI"

        (
            scgi_bind_address,
            scgi_port,
            request_timeout_s,
            config_check_period_s,
            reply_with_descriptions,
            tls_enabled,
        ) = default.props()

        scgi_bind_addr_from_conf = cp.get(
            section, "bind_address", fallback=scgi_bind_address
        )

        return cls(
            "0.0.0.0" if scgi_bind_addr_from_conf == "" else scgi_bind_addr_from_conf,
            cp.getint(section, "port", fallback=scgi_port),
            cp.getint(section, "timeout_s", fallback=request_timeout_s),
            cp.getint(section, "config_check_period_s", fallback=config_check_period_s),
            cp.getboolean(
                section, "reply_with_descriptions", fallback=reply_with_descriptions
            ),
            cp.getboolean(section, "tls_enabled", fallback=tls_enabled),
        )
