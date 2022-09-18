import re
from configparser import ParsingError
from dataclasses import dataclass
from typing import List

from ..config.static_plc_config import StaticPlcConfig
from ..errors import ConfigError

section_pattern = re.compile(r"^c\d+$")


@dataclass(frozen=True)
class StaticPlcsConfig:
    static_plcs_configs: List[StaticPlcConfig]

    def __str__(self):
        header = "STATIC PLC CONFIG\n"
        plcs = "\n\n".join((str(plc) for plc in self.static_plcs_configs))

        return header + plcs

    @classmethod
    def load(cls, cp):
        try:
            return StaticPlcsConfig(
                [
                    StaticPlcConfig.load(cp, section)
                    for section in cp.sections()
                    if is_section_static_plc(section)
                ]
            )
        except ParsingError as e:
            raise ConfigError("Can't read config file") from e


def is_section_static_plc(section):
    return section_pattern.match(section) is not None
