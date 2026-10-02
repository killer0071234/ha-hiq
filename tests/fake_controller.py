"""In-memory fake of a Cybro SCGI server with a HIQ controller attached."""

from __future__ import annotations

from collections.abc import Iterable
from http import HTTPStatus
from xml.sax.saxutils import escape

from aiohttp import ClientConnectionError
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)
from yarl import URL

from .const import HOST, NAD, PORT

# Controller variables (without the "c<nad>." prefix) and their initial values.
HIQ_TAGS: dict[str, str] = {
    # on/off light
    "lc00_qx00": "1",
    "lc00_general_error": "0",
    # rgb light (dimmer + hue + saturation)
    "ld00_qw00": "50",
    "ld00_qw01": "50",
    "ld00_qw02": "80",
    "ld00_rgb_mode": "1",
    "ld00_general_error": "0",
    # dimmable light
    "ld01_qw00": "40",
    "ld01_rgb_mode": "0",
    "ld01_general_error": "0",
    # module with a general error -> its light must not be created
    "lc01_qx00": "0",
    "lc01_general_error": "1",
    # blind
    "bc00_blinds_position_00": "40",
    "bc00_blinds_setpoint_00": "40",
    "bc00_qxs00_up": "0",
    "bc00_qxs00_dn": "0",
    "bc00_general_error": "0",
    # thermostat
    "th00_general_error": "0",
    "th00_ix00": "0",
    "th00_output": "1",
    "th00_active": "1",
    "th00_setpoint_lo": "160",
    "th00_setpoint_hi": "280",
    "th00_temperature": "215",
    "th00_temperature_1": "210",
    "th00_floor_tmp": "220",
    "th00_humidity": "45",
    "th00_light_sensor": "100",
    "th00_setpoint": "220",
    "th00_setpoint_idle": "180",
    "th00_setpoint_offset": "0",
    "th00_setpoint_active": "220",
    "th00_fan_limit": "0",
    "th00_fan_options": "0",
    "th00_temperature_source": "0",
    "th00_display_mode": "0",
    "th00_window_enable": "1",
    "th00_demand_enable": "0",
    "th00_hysteresis": "5",
    "th00_max_temp": "300",
    "th00_max_time": "60",
    "th00_config1_req": "0",
    "th00_options_back_req": "0",
    # hvac
    "hvac_mode": "1",
    "hvac_temperature_source": "0",
    "hvac_display_mode": "0",
    "hvac_fan_option_b01": "0",
    "outdoor_temperature_enable": "1",
    "auto_limits_enable": "0",
    "outdoor_temperature": "125",
    "setpoint_idle_heating": "180",
    # weather station
    "weather_temperature": "150",
    "weather_humidity": "60",
    "weather_wind_speed": "12",
    "weather_wind_direction": "90",
    "weather_pressure": "10130",
    # power meter
    "power_meter_error": "0",
    "power_meter_power": "1200",
    "power_meter_voltage": "2300",
    "power_meter_current": "52",
    # controller diagnostics
    "scan_time": "5",
    "scan_time_max": "9",
    "scan_frequency": "200",
    "cybro_uptime": "1000",
    "operating_hours": "10",
    "scan_overrun": "0",
    "retentive_fail": "0",
    "general_error": "0",
    "cybro_power_supply": "240",
    "iex_power_supply": "240",
    # outdoor sensor module
    "op00_general_error": "0",
    "op00_temperature": "200",
    "op00_humidity": "40",
}


def alc_file(names: Iterable[str]) -> str:
    """Return an allocation file in the format the controller reports it."""
    lines = [
        ";CPU CyBro-3 10000",
        ";Addr Id    Array Offset Size Scope  Type  Name                             Description",
    ]
    lines += [
        f"0050  00000 1     0      1    global int   {name:<32} Description of {name}"
        for name in names
    ]
    return "\n".join(lines)


class FakeController:
    """Answer SCGI requests from the integration's aiohttp session."""

    def __init__(self, tags: dict[str, str] | None = None) -> None:
        """Initialize a server with one controller."""
        self.online = True
        self.status = HTTPStatus.OK
        self.values: dict[str, str] = {
            "sys.scgi_port_status": "active",
            "sys.server_uptime": "00 days, 01:02:03",
            "sys.scgi_request_pending": "0",
            "sys.scgi_request_count": "1",
            "sys.push_port_status": "active",
            "sys.push_count": "0",
            "sys.push_ack_errors": "0",
            "sys.push_list_count": "0",
            "sys.cache_request": "0",
            "sys.cache_valid": "1",
            "sys.server_version": "3.1.3",
            "sys.udp_rx_count": "0",
            "sys.udp_tx_count": "0",
            "sys.datalogger_status": "stopped",
        }
        self.writes: list[tuple[str, str]] = []
        self.add_controller(NAD, HIQ_TAGS if tags is None else tags)

    def add_controller(self, nad: int, tags: dict[str, str]) -> None:
        """Add a controller with the given variables."""
        prefix = f"c{nad}."
        self.values |= {
            f"{prefix}sys.ip_port": "192.168.1.10:8442",
            f"{prefix}sys.timestamp": "2026-10-02 12:00:00",
            f"{prefix}sys.plc_program_status": "ok",
            f"{prefix}sys.response_time": "3",
            f"{prefix}sys.bytes_transferred": "200",
            f"{prefix}sys.comm_error_count": "0",
            f"{prefix}sys.alc_file": alc_file(tags),
        }
        self.values |= {f"{prefix}{name}": value for name, value in tags.items()}

    def register(self, aioclient_mock: AiohttpClientMocker) -> None:
        """Route all requests to the SCGI server to this fake."""
        aioclient_mock.get(f"http://{HOST}:{PORT}/", side_effect=self.handle)

    def written(self, name: str) -> list[str]:
        """Return all values written to a variable, in order."""
        return [value for var, value in self.writes if var == name]

    async def handle(
        self, method: str, url: URL, data: object
    ) -> AiohttpClientMockResponse:
        """Answer a single read / write request."""
        if not self.online:
            raise ClientConnectionError("controller offline")
        names = []
        for name, value in url.query.items():
            if value != "":
                self.values[name] = value
                self.writes.append((name, value))
            names.append(name)
        body = "".join(
            f"<var><name>{escape(name)}</name>"
            f"<value>{escape(self.values.get(name, '?'))}</value>"
            f"<description>Description of {escape(name)}</description></var>"
            for name in names
        )
        return AiohttpClientMockResponse(
            method,
            url,
            status=self.status,
            text=f"<data>{body}</data>",
            headers={"Content-Type": "text/xml"},
        )
