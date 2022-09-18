import re
from itertools import chain

from ......services.rw_service.subservices.plc_comm_service.alc_service.var_info import (
    VarInfo,
)
from ......services.rw_service.subservices.plc_comm_service.data_type import (
    DATA_TYPE_SIZES,
)
from ......services.rw_service.subservices.plc_comm_service.data_type import DataType


class AlcParser:
    ALC_PATTERN = re.compile(
        "^(\\w*)\\s*(\\w*)\\s*(\\w*)\\s*(\\w*)\\s*(\\w*)\\s*(\\w*)\\s*(\\w*)\\s*([\\w.]*)\\s*(.*)"
    )

    @classmethod
    def parse(cls, text):
        lines = text.splitlines()

        var_infos = chain(*(cls._parse_line(line) for line in lines))

        return {var_info.name: var_info for var_info in var_infos}

    @classmethod
    def _parse_line(cls, line):
        line = line.rstrip()

        if len(line) == 0 or line[0] == ";":
            return iter(())

        groups = cls.ALC_PATTERN.search(line).group
        name = groups(8)
        address = int(groups(1), 16)
        entry_id = int(groups(2), 16)
        array_size = int(groups(3))
        is_array = array_size > 1
        offset = int(groups(4))
        size = int(groups(5))
        scope = groups(6)
        data_type_name = groups(7)
        description = groups(9)

        # add offset for timers and counters
        address += offset

        try:
            data_type = DataType[data_type_name.upper()]
            size = DATA_TYPE_SIZES[data_type]
        except KeyError:
            data_type = DataType.NONE

        if not is_array:
            yield VarInfo(
                entry_id,
                name,
                is_array,
                array_size,
                address,
                offset,
                size,
                scope,
                data_type,
                description,
            )
        else:
            for i in range(array_size):
                yield VarInfo(
                    entry_id,
                    f"{name}[{str(i)}]",
                    is_array,
                    array_size,
                    address + i * size,
                    offset,
                    size,
                    scope,
                    data_type,
                    description,
                )
