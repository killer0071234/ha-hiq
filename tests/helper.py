"""Helpers for tests."""
from __future__ import annotations

import logging
from typing import Any, Final, TypeVar
from unittest.mock import MagicMock, Mock, patch

from hahomematic import const as hahomematic_const
from hahomematic.central import CentralConfig
from hahomematic.client import InterfaceConfig, _ClientConfig
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.entity import BaseParameterEntity
from hahomematic_support.client_local import ClientLocal, LocalRessources
from pytest_homeassistant_custom_component.common import MockConfigEntry
from cybro import Device, Var

from custom_components.hiq.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests import const

_LOGGER = logging.getLogger(__name__)

EXCLUDE_METHODS_FROM_MOCKS: Final = [
    "default_platform",
    "event",
    "fire_refresh_entity_callback",
    "fire_remove_entity_callback",
    "fire_update_entity_callback",
    "get_event_data",
    "get_on_time_and_cleanup",
    "is_state_change",
    "load_entity_value",
    "register_internal_update_callback",
    "register_refresh_callback",
    "register_remove_callback",
    "register_update_callback",
    "set_usage",
    "unregister_internal_update_callback",
    "unregister_refresh_callback",
    "unregister_remove_callback",
    "unregister_update_callback",
    "update_value",
]
T = TypeVar("T")

# pylint: disable=protected-access


def var_dict() -> dict[str, str]:
    """Return variable values as ditionary."""
    _vars: dict[str, Any] = {
        "sys.scgi_port_status": "active",
        "sys.server_uptime": "00 days, 01:02:03",
        "sys.scgi_request_pending": 12,
        "sys.scgi_request_count": 23,
        "sys.push_port_status": "inactive",
        "sys.push_count": 13,
        "sys.push_ack_errors": 14,
        "sys.push_list_count": 2,
        "sys.cache_request": 1,
        "sys.cache_valid": 2,
        "sys.server_version": "3.1.3",
        "sys.udp_rx_count": 123,
        "sys.udp_tx_count": 234,
        "sys.datalogger_status": "stopped",
        "c1000.sys.ip_port": "127.0.0.1:8442",
        "c1000.sys.timestamp": "2022-08-20 15:52:46",
        "c1000.sys.plc_program_status": "ok",
        "c1000.sys.response_time": 3,
        "c1000.sys.bytes_transferred": 200,
        "c1000.sys.comm_error_count": 22,
        "c1000.sys.alc_file": ";CPU CyBro-2 10000 \n;Addr Id    Array Offset Size Scope  Type  Name                             \n0050  00000 1     0      1    global bit   lc00_general_error               Combined system error (timeout or program error), module is not operational.\n0070  00000 1     0      1    global bit   lc01_general_error               Combined system error (timeout or program error), module is not operational.\n0090  00000 1     0      1    global bit   lc02_general_error               Combined system error (timeout or program error), module is not operational.\n00B0  00000 1     0      1    global bit   lc03_general_error               Combined system error (timeout or program error), module is not operational.\n00D0  00000 1     0      1    global bit   lc04_general_error               Combined system error (timeout or program error), module is not operational.\n00F0  00000 1     0      1    global bit   lc05_general_error               Combined system error (timeout or program error), module is not operational.\n0110  00000 1     0      1    global bit   lc06_general_error               Combined system error (timeout or program error), module is not operational.\n0130  00000 1     0      1    global bit   lc07_general_error               Combined system error (timeout or program error), module is not operational.\n0150  00000 1     0      1    global bit   ld00_general_error               Combined system error (timeout or program error), module is not operational.\n0170  00000 1     0      1    global bit   ld01_general_error               Combined system error (timeout or program error), module is not operational.\n0190  00000 1     0      1    global bit   ld02_general_error               Combined system error (timeout or program error), module is not operational.\n01B0  00000 1     0      1    global bit   ld03_general_error               Combined system error (timeout or program error), module is not operational.\n01D0  00000 1     0      1    global bit   bc00_general_error               Combined system error (timeout or program error), module is not operational.\n01F0  00000 1     0      1    global bit   bc01_general_error               Combined system error (timeout or program error), module is not operational.\n0210  00000 1     0      1    global bit   bc02_general_error               Combined system error (timeout or program error), module is not operational.",
    }
    return _vars


def api_resp(new_val: dict[str, str] | None = None) -> dict:
    """Return a full response."""
    _dict = var_dict()
    if new_val is not None:
        for k, v in new_val.items():
            print(k, v)
            _dict[k] = v
            # _dict.update(k, v)
    _all1 = {
        "var": [
            {"name": k, "value": v, "description": "Desc."} for k, v in _dict.items()
        ]
    }
    return _all1


def var_vars() -> dict[str, Var]:
    """Return variable values as Var structure."""
    _dict = var_dict()
    _vars = {k: Var(k, v, "Desc.") for k, v in _dict.items()}
    return _vars


def get_cybro_device(new_val: dict[str, str] | None = None) -> Device:
    """Return a cybro device."""
    return Device(
        data=api_resp(new_val),
        plc_nad=1000,
    )
