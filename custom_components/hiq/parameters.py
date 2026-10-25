"""Parameters of the outputs of HIQ-Home light and blind modules."""

from __future__ import annotations

from re import search

from homeassistant.helpers.device_registry import DeviceInfo

from .coordinator import HiqDataUpdateCoordinator
from .cover import blind_device_info
from .light import is_general_error_ok
from .light import light_device_info

# LD config group of a parameter, written with ldNN_config_group
LD_CONFIG_GROUPS = {"input_mode": 0, "output_timer": 1, "color_mode": 2}


def find_module_parameters(
    coordinator: HiqDataUpdateCoordinator, names: tuple[str, ...]
) -> list[tuple[str, str, str, int]]:
    """Find parameters of the outputs of working modules.

    eg: c1000.lc00_input_mode_03 -> (key, "c1000.lc00", "input_mode", 3)
    """
    res: list[tuple[str, str, str, int]] = []
    for key in coordinator.data.plc_info.plc_vars:
        match = search(r"^(c\d+\.(?:lc|ld|bc)\d+)_([a-z_]+)_(\d+)$", key)
        if not match or match.group(2) not in names:
            continue
        if not is_general_error_ok(coordinator, key):
            continue
        module, name, output = match.groups()
        res.append((key, module, name, int(output)))
    return res


def module_parameter_tags(
    module: str, name: str, output: int, value: int
) -> dict[str, str]:
    """Return the tags writing a parameter of a module output.

    The parameters of all outputs are written through the same registers:
    select the output (and parameter), write the data, then request the write.
    eg: c1000.lc00, input_mode, 3, 1 -> lc00_input_mode_index = 3,
    lc00_input_mode_data = 1, lc00_input_mode_req = 1
    """
    kind = module.split(".")[-1][:2]
    if kind == "ld":
        tags = {
            f"{module}_config_group": str(LD_CONFIG_GROUPS[name]),
            f"{module}_config_index": str(output),
        }
        prefix = f"{module}_config"
    elif kind == "bc":
        # blinds time up (bottom to top) is index 0..4, down is 5..9
        offset = 5 if name == "blinds_time_dn" else 0
        tags = {f"{module}_blinds_time_index": str(output + offset)}
        prefix = f"{module}_blinds_time"
    else:
        tags = {f"{module}_{name}_index": str(output)}
        prefix = f"{module}_{name}"
    return tags | {f"{prefix}_data": str(value), f"{prefix}_req": "1"}


def output_device_info(
    coordinator: HiqDataUpdateCoordinator, module: str, output: int
) -> DeviceInfo:
    """Return the device info of the light or blind of a module output."""
    kind = module.split(".")[-1][:2]
    if kind == "bc":
        return blind_device_info(coordinator, f"{module}_blinds_position_{output:02d}")
    out = "qw" if kind == "ld" else "qx"
    return light_device_info(coordinator, f"{module}_{out}{output:02d}")
