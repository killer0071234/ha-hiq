import re
from dataclasses import dataclass
from textwrap import dedent
from typing import Optional

from ..errors import InvalidPassword
from ..errors import InvalidPlcName


@dataclass(frozen=True)
class StaticPlcConfig:
    @classmethod
    def create(cls, password, name, ip, port):
        try:
            password = None if password == "" else int(password)
        except ValueError:
            raise InvalidPassword(password)

        return cls(password, name, ip, port, cls._extract_nad_from_name(name))

    password: Optional[int]
    name: str
    ip: str
    port: int
    nad: int

    def __str__(self):
        ip = self.ip if self.ip != "" else "_"

        return dedent(
            f"""\
                [{self.name}]
                  {ip}:{self.port}
                  password = {self.password}
                """
        )

    def props(self):
        return (
            "" if self.password is None else str(self.password),
            self.name,
            self.ip,
            self.port,
        )

    @classmethod
    def load(cls, cp, section):
        return cls.create(
            cp.get(section, "password"),
            section,
            cp.get(section, "ip"),
            cp.getint(section, "port"),
        )

    @classmethod
    def _extract_nad_from_name(cls, name):
        match = re.search(r"^c(\d+)$", name)

        if match is None:
            raise InvalidPlcName(name)

        try:
            return int(match.group(1))
        except ValueError:
            raise InvalidPlcName(name)
