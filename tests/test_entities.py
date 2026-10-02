"""Tests for HIQ-Home sensors, numbers, selects, switches, buttons and weather."""

from __future__ import annotations

import logging

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

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
        ("c1000.th00_setpoint_idle", "195.0"),
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


@pytest.mark.xfail(
    reason="0.1 scaled values are not rounded, 21.1 is written as 211.00000000000003",
    strict=True,
)
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


@pytest.mark.xfail(
    reason="min_value / max_value are ignored by Home Assistant, "
    "native_min_value / native_max_value must be used",
    strict=True,
)
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


@pytest.mark.xfail(
    reason="button debug log has 3 placeholders but 2 arguments", strict=True
)
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


@pytest.mark.xfail(
    reason="condition returns '' instead of None, so the state is empty",
    strict=True,
)
async def test_weather_state(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the weather state is unknown, the station has no condition."""
    assert hass.states.get("weather.weather_c1000_weather").state == "unknown"


MODULE_SENSORS = {
    "sensor.weather_c1000_temperatures_temperature": ("20.0", "°C"),
    "sensor.weather_c1000_temperatures_humidity": ("40", "%"),
    "sensor.energy_c1000_power_meter_power": ("1200", "W"),
    "sensor.energy_c1000_power_meter_voltage": ("230.0", "V"),
    "sensor.energy_c1000_power_meter_current": ("52", "mA"),
}


async def test_module_sensors_after_reload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test sensors of temperature modules and the power meter."""
    assert await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()
    await refresh(hass, init_integration)

    states = {
        entity_id: (state.state, state.attributes.get("unit_of_measurement"))
        for entity_id in MODULE_SENSORS
        if (state := hass.states.get(entity_id))
    }
    assert states == MODULE_SENSORS


@pytest.mark.xfail(
    reason="the module status is checked before it was read from the controller, "
    "so these sensors are only created after a reload",
    strict=True,
)
async def test_module_sensors_on_first_setup(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test sensors of temperature modules and the power meter are created."""
    assert all(hass.states.get(entity_id) for entity_id in MODULE_SENSORS)
