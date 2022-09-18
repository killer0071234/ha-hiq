from dataclasses import dataclass


@dataclass(frozen=True)
class DbaseConfig:
    dbase_enabled: bool
    host: str
    port: int
    name: str
    user: str
    password: str
    max_query_size: int

    def props(self):
        return (
            self.dbase_enabled,
            self.host,
            self.port,
            self.name,
            self.user,
            self.password,
            self.max_query_size,
        )

    @classmethod
    def load(cls, cp, default):
        section = "DBASE"

        (
            dbase_enabled,
            host,
            port,
            name,
            user,
            password,
            max_query_size,
        ) = default.props()

        return cls(
            cp.getboolean(section, "enabled", fallback=dbase_enabled),
            cp.get(section, "host", fallback=host),
            cp.getint(section, "port", fallback=port),
            cp.get(section, "name", fallback=name),
            cp.get(section, "user", fallback=user),
            cp.get(section, "password", fallback=password),
            cp.getint(section, "max_query_size", fallback=max_query_size),
        )
