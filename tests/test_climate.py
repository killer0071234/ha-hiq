"""Tests for HIQ-Home thermostats."""

from __future__ import annotations

import pytest
from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hiq.const import ATTR_FLOOR_TEMP, ATTR_SETPOINT_IDLE

from .common import call_service, refresh
from .fake_controller import FakeController

THERMOSTAT = "climate.climate_c1000_th00_thermostat"
TH = "c1000.th00"


async def _set(
    hass: HomeAssistant,
    controller: FakeController,
    entry: MockConfigEntry,
    **values: str,
) -> None:
    """Change controller variables (th00_* or hvac_mode) and poll."""
    for name, value in values.items():
        controller.values[f"c1000.{name}"] = value
    await refresh(hass, entry)


async def test_thermostat_heating(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a heating thermostat in comfort mode."""
    state = hass.states.get(THERMOSTAT)
    assert state.state == HVACMode.HEAT
    assert state.attributes["hvac_modes"] == [HVACMode.OFF, HVACMode.HEAT]
    assert state.attributes["hvac_action"] == HVACAction.HEATING
    assert state.attributes["current_temperature"] == 21.5
    assert state.attributes["current_humidity"] == 45
    assert state.attributes["temperature"] == 22.0
    assert state.attributes["min_temp"] == 16.0
    assert state.attributes["max_temp"] == 28.0
    assert state.attributes["preset_mode"] == "comfort"
    assert state.attributes["preset_modes"] == ["comfort", "eco"]
    assert state.attributes[ATTR_FLOOR_TEMP] == 22.0
    assert state.attributes[ATTR_SETPOINT_IDLE] == 18.0


async def test_thermostat_cooling(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test the hvac mode of the controller switches the thermostat to cooling."""
    await _set(hass, controller, init_integration, hvac_mode="2")

    state = hass.states.get(THERMOSTAT)
    assert state.state == HVACMode.COOL
    assert state.attributes["hvac_modes"] == [HVACMode.OFF, HVACMode.COOL]
    assert state.attributes["hvac_action"] == HVACAction.COOLING


async def test_thermostat_idle_and_off(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test eco mode when the thermostat is not active."""
    await _set(
        hass,
        controller,
        init_integration,
        th00_active="0",
        th00_output="0",
        th00_setpoint_active="0",
    )

    state = hass.states.get(THERMOSTAT)
    assert state.state == HVACMode.OFF
    assert state.attributes["hvac_action"] == HVACAction.IDLE
    assert state.attributes["preset_mode"] == "eco"
    assert state.attributes["temperature"] == 18.0


async def test_thermostat_boost_needs_fan_max(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test boost is offered only if fan max is enabled (fan options bit 4)."""
    await _set(hass, controller, init_integration, th00_fan_options="16")
    assert hass.states.get(THERMOSTAT).attributes["preset_modes"] == [
        "comfort",
        "boost",
        "eco",
    ]

    await _set(hass, controller, init_integration, th00_fan_limit="4")
    assert hass.states.get(THERMOSTAT).attributes["preset_mode"] == "boost"


@pytest.mark.parametrize(
    ("service", "data", "written"),
    [
        ("set_hvac_mode", {"hvac_mode": "off"}, ("th00_active", "0")),
        ("set_hvac_mode", {"hvac_mode": "heat"}, ("th00_active", "1")),
        ("turn_off", {}, ("th00_active", "0")),
        ("turn_on", {}, ("th00_active", "1")),
        ("set_preset_mode", {"preset_mode": "eco"}, ("th00_active", "0")),
        ("set_preset_mode", {"preset_mode": "comfort"}, ("th00_active", "1")),
    ],
)
async def test_thermostat_control(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
    service: str,
    data: dict,
    written: tuple[str, str],
) -> None:
    """Test mode changes are written to the thermostat."""
    await call_service(hass, "climate", service, THERMOSTAT, **data)

    assert controller.writes == [(f"c1000.{written[0]}", written[1])]


async def test_set_temperature_comfort(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test the comfort setpoint is written in tenth degrees."""
    await call_service(hass, "climate", "set_temperature", THERMOSTAT, temperature=21)

    assert controller.writes == [(f"{TH}_setpoint", "210")]


async def test_set_temperature_eco(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test the eco setpoint is written with the config write request."""
    await _set(hass, controller, init_integration, th00_active="0")

    await call_service(hass, "climate", "set_temperature", THERMOSTAT, temperature=17.5)

    assert controller.writes == [
        (f"{TH}_setpoint_idle", "175"),
        (f"{TH}_config2_req", "1"),
    ]


async def test_set_temperature_boost(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test boost while heating changes the upper setpoint limit."""
    await _set(
        hass, controller, init_integration, th00_fan_options="16", th00_fan_limit="4"
    )

    await call_service(hass, "climate", "set_temperature", THERMOSTAT, temperature=26)

    assert controller.writes == [
        (f"{TH}_setpoint_hi", "260"),
        (f"{TH}_config2_req", "1"),
    ]


async def test_thermostat_hvac_off(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test the thermostat is off when hvac is switched off on the controller."""
    await _set(hass, controller, init_integration, hvac_mode="0")

    state = hass.states.get(THERMOSTAT)
    assert state.state == HVACMode.OFF
    assert state.attributes["hvac_modes"] == [HVACMode.OFF]


@pytest.mark.parametrize(
    ("values", "state", "action"),
    [
        ({"hvac_mode": "3"}, "unknown", None),
        ({"th00_active": "2"}, "unknown", HVACAction.HEATING),
        ({"th00_output": "2"}, HVACMode.HEAT, None),
    ],
    ids=["hvac_mode", "active", "output"],
)
async def test_thermostat_unexpected_values(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
    values: dict[str, str],
    state: str,
    action: HVACAction | None,
) -> None:
    """Test unexpected values on the controller result in an unknown state."""
    await _set(hass, controller, init_integration, **values)

    thermostat = hass.states.get(THERMOSTAT)
    assert thermostat.state == state
    assert thermostat.attributes.get("hvac_action") == action
