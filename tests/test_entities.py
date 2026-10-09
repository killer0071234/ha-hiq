"""Tests for HIQ-Home sensors, numbers, selects, switches, buttons and weather."""

from __future__ import annotations

from collections import Counter
import logging

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hiq.const import DOMAIN

from .common import call_service, refresh
from .fake_controller import FakeController

TH = "climate_c1000_th00_thermostat"
DIAG = "system_c1000_diagnostic"


@pytest.mark.parametrize(
    ("entity_id", "state", "unit"),
    [
        (f"sensor.{TH}_temperature", "21.5", "°C"),
        (f"sensor.{TH}_external_temperature", "21.0", "°C"),
        (f"sensor.{TH}_humidity", "45", "%"),
        ("sensor.climate_c1000_hvac_outdoor_temperature", "12.5", "°C"),
        (f"sensor.{DIAG}_scan_time", "5", "ms"),
        (f"sensor.{DIAG}_scan_time_maximum", "9", "ms"),
        (f"sensor.{DIAG}_controller_program_cycles", "200", "Hz"),
        (f"sensor.{DIAG}_controller_supply_voltage", "24.0", "V"),
        (f"sensor.{DIAG}_iex_voltage", "24.0", "V"),
        (f"sensor.{DIAG}_controller_operation_hours", "10", "h"),
        (f"sensor.{DIAG}_controller_address", "192.168.1.10:8442", None),
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_id: str,
    state: str,
    unit: str | None,
) -> None:
    """Test sensor values are scaled and have units."""
    sensor = hass.states.get(entity_id)
    assert sensor.state == state
    assert sensor.attributes.get("unit_of_measurement") == unit


async def test_sensor_unknown_value(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test '?' from the SCGI server (unknown value) results in unknown state."""
    controller.values["c1000.th00_temperature"] = "?"
    await refresh(hass, init_integration)

    assert hass.states.get(f"sensor.{TH}_temperature").state == "unknown"


@pytest.mark.parametrize(
    ("entity_id", "variable", "values"),
    [
        (f"binary_sensor.{DIAG}_lc00_general_error", "lc00_general_error", ("0", "1")),
        (
            f"binary_sensor.{DIAG}_controller_retentive_memory_failure",
            "retentive_fail",
            ("0", "1"),
        ),
        (f"binary_sensor.{TH}_output", "th00_output", ("0", "1")),
        # window contact is closed (1) when the window is closed
        (f"binary_sensor.{TH}_window", "th00_ix00", ("1", "0")),
    ],
)
async def test_binary_sensors(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
    entity_id: str,
    variable: str,
    values: tuple[str, str],
) -> None:
    """Test binary sensors follow their variable."""
    off, on = values
    for value, expected in ((off, "off"), (on, "on")):
        controller.values[f"c1000.{variable}"] = value
        await refresh(hass, init_integration)
        assert hass.states.get(entity_id).state == expected


async def test_number_with_write_request(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test thermostat settings are written together with their write request."""
    entity_id = f"number.{TH}_setpoint_eco"
    assert hass.states.get(entity_id).state == "18.0"

    await call_service(hass, "number", "set_value", entity_id, value=19.5)

    assert controller.writes == [
        ("c1000.th00_setpoint_idle", "195"),
        ("c1000.th00_config2_req", "1"),
    ]
    assert hass.states.get(entity_id).state == "19.5"


async def test_number_int(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test integer settings are written as integer."""
    entity_id = f"number.{TH}_activation_time_max_function"
    assert hass.states.get(entity_id).state == "60"

    await call_service(hass, "number", "set_value", entity_id, value=45)

    assert controller.writes == [
        ("c1000.th00_max_time", "45"),
        ("c1000.th00_config2_req", "1"),
    ]


async def test_number_written_in_whole_tenths(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test 0.1 scaled values are written as whole numbers."""
    await call_service(
        hass, "number", "set_value", f"number.{TH}_setpoint_eco", value=21.1
    )

    assert controller.written("c1000.th00_setpoint_idle") == ["211"]


async def test_number_limits(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test temperature setpoints are limited to 0 .. 40 °C."""
    state = hass.states.get(f"number.{TH}_setpoint_eco")

    assert (state.attributes["min"], state.attributes["max"]) == (0.0, 40.0)


async def test_select(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test a select maps options to controller values."""
    entity_id = f"select.{TH}_fan_mode_limit"
    state = hass.states.get(entity_id)
    assert state.state == "off"
    assert state.attributes["options"] == ["off", "fan1", "fan2", "fan3", "max"]

    await call_service(hass, "select", "select_option", entity_id, option="fan2")

    assert controller.written("c1000.th00_fan_limit") == ["2"]
    assert hass.states.get(entity_id).state == "fan2"


async def test_select_with_write_request(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test thermostat config selects also set their write request."""
    entity_id = f"select.{TH}_temperature_source_sensor"
    assert hass.states.get(entity_id).state == "internal_sensor"

    await call_service(
        hass, "select", "select_option", entity_id, option="external_sensor"
    )

    assert controller.writes == [
        ("c1000.th00_temperature_source", "1"),
        ("c1000.th00_config1_req", "1"),
    ]


async def test_hvac_temperature_source_select(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test the global temperature source of the controller is a select."""
    entity_id = er.async_get(hass).async_get_entity_id(
        "select", DOMAIN, "c1000.hvac_temperature_source"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "internal_sensor"

    await call_service(
        hass, "select", "select_option", entity_id, option="remote_sensor"
    )

    assert controller.written("c1000.hvac_temperature_source") == ["2"]


async def test_select_unknown_value(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test a value without option results in an unknown state."""
    controller.values["c1000.hvac_mode"] = "7"
    await refresh(hass, init_integration)

    assert hass.states.get("select.climate_c1000_hvac_operation_mode_hvac").state == (
        "unknown"
    )


async def test_switch(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test a switch is written as 0 / 1."""
    entity_id = "switch.climate_c1000_hvac_enable_outdoor_temperature"
    assert hass.states.get(entity_id).state == "on"

    await call_service(hass, "switch", "turn_off", entity_id)
    assert hass.states.get(entity_id).state == "off"
    await call_service(hass, "switch", "turn_on", entity_id)
    assert hass.states.get(entity_id).state == "on"

    assert controller.written("c1000.outdoor_temperature_enable") == ["0", "1"]


async def test_switch_with_write_request(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test thermostat config switches also set their write request."""
    entity_id = f"switch.{TH}_window_switch_enable"

    await call_service(hass, "switch", "turn_off", entity_id)

    assert controller.writes == [
        ("c1000.th00_window_enable", "0"),
        ("c1000.th00_config3_req", "1"),
    ]


async def test_button(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test pressing a button writes 1 to its variable."""
    await call_service(hass, "button", "press", f"button.{TH}_config_write_request")

    assert controller.writes == [("c1000.th00_config1_req", "1")]


async def test_button_debug_log(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    init_integration: MockConfigEntry,
) -> None:
    """Test pressing a button logs a valid debug message."""
    caplog.set_level(logging.DEBUG, logger="custom_components.hiq")

    await call_service(hass, "button", "press", f"button.{TH}_config_write_request")

    for record in caplog.records:
        record.getMessage()


async def test_weather(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """Test the weather station of the controller."""
    state = hass.states.get("weather.weather_c1000_weather")

    assert state.attributes["temperature"] == 15.0
    assert state.attributes["humidity"] == 60
    assert state.attributes["wind_speed"] == 1.2
    assert state.attributes["wind_bearing"] == 90


async def test_weather_state(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the weather state is unknown, the station has no condition."""
    assert hass.states.get("weather.weather_c1000_weather").state == "unknown"


MODULE_SENSORS = {
    "sensor.weather_c1000_temperatures_op00_temperature": ("20.0", "°C"),
    "sensor.weather_c1000_temperatures_op00_humidity": ("40", "%"),
    "sensor.energy_c1000_power_meter_power": ("1200", "W"),
    "sensor.energy_c1000_power_meter_voltage": ("230.0", "V"),
    "sensor.energy_c1000_power_meter_current": ("52", "mA"),
}


async def test_module_sensors(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test sensors of temperature modules and the power meter on first setup."""
    states = {
        entity_id: (state.state, state.attributes.get("unit_of_measurement"))
        for entity_id in MODULE_SENSORS
        if (state := hass.states.get(entity_id))
    }
    assert states == MODULE_SENSORS


async def test_three_phase_power_meter_voltage(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the voltages of all phases are scaled like the mean voltage.

    The SCGI server lists all variables without a value on a full update,
    the phase voltages must be read before the sensors are set up.
    """
    entity_registry = er.async_get(hass)
    voltages = {}
    for phase in ("", "1", "2", "3"):
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"c1000.power_meter_voltage{phase}"
        )
        voltages[phase] = hass.states.get(entity_id).state
    assert voltages == {"": "230.0", "1": "242.0", "2": "239.0", "3": "239.0"}


POWER_METER_NAMES = {
    "power_meter_power": "Power",
    "power_meter_power1": "Power L1",
    "power_meter_power2": "Power L2",
    "power_meter_power3": "Power L3",
    "power_meter_voltage": "Voltage",
    "power_meter_voltage1": "Voltage L1",
    "power_meter_voltage2": "Voltage L2",
    "power_meter_voltage3": "Voltage L3",
    "power_meter_current": "Current",
    "power_meter_current1": "Current L1",
    "power_meter_current2": "Current L2",
    "power_meter_current3": "Current L3",
    "power_meter_energy": "Energy",
    "power_meter_energy_real": "Energy real",
    "power_meter_energy_watthours": "Energy (Wh)",
}


async def test_power_meter_names(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test every power meter sensor has its own name, phases are named L1..L3."""
    entity_registry = er.async_get(hass)
    names = {}
    for tag in POWER_METER_NAMES:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"c1000.{tag}"
        )
        friendly_name = hass.states.get(entity_id).attributes["friendly_name"]
        names[tag] = friendly_name.removeprefix("c1000 power meter ")
    assert names == POWER_METER_NAMES


TEMPERATURE_NAMES = {
    "op00_temperature": "op00 temperature",
    "op00_humidity": "op00 humidity",
    "ts00_temperature_0": "ts00 internal temperature",
    "ts00_temperature_1": "ts00 external temperature",
}


async def test_temperature_module_names(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test sensors of temperature modules are named after their module."""
    entity_registry = er.async_get(hass)
    names = {}
    for tag in TEMPERATURE_NAMES:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"c1000.{tag}"
        )
        friendly_name = hass.states.get(entity_id).attributes["friendly_name"]
        names[tag] = friendly_name.removeprefix("c1000 temperatures ")
    assert names == TEMPERATURE_NAMES


async def test_entity_names_unique(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test no two entities share a name (Home Assistant would number them)."""
    entity_registry = er.async_get(hass)
    names = Counter(
        hass.states.get(entry.entity_id).attributes["friendly_name"]
        for entry in er.async_entries_for_config_entry(
            entity_registry, init_integration.entry_id
        )
    )

    assert [name for name, count in names.items() if count > 1] == []
