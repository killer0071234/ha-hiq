"""Tests for HIQ-Home thermostats."""

from __future__ import annotations

import pytest
from homeassistant.components.climate import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
    assert state.attributes["hvac_modes"] == [HVACMode.HEAT]
    assert state.attributes["supported_features"] == (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
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


async def test_thermostat_limits_follow_controller(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test changed setpoint limits are shown after a single poll."""
    await _set(
        hass,
        controller,
        init_integration,
        th00_setpoint_lo="100",
        th00_setpoint_hi="300",
    )

    state = hass.states.get(THERMOSTAT)
    assert state.attributes["min_temp"] == 10.0
    assert state.attributes["max_temp"] == 30.0


async def test_thermostat_cooling(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test the hvac mode of the controller switches the thermostat to cooling."""
    await _set(hass, controller, init_integration, hvac_mode="2")

    state = hass.states.get(THERMOSTAT)
    assert state.state == HVACMode.COOL
    assert state.attributes["hvac_modes"] == [HVACMode.COOL]
    assert state.attributes["hvac_action"] == HVACAction.COOLING


async def test_thermostat_eco(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test a not active thermostat keeps heating to the eco (idle) setpoint."""
    await _set(
        hass,
        controller,
        init_integration,
        th00_active="0",
        th00_output="0",
        th00_setpoint_active="0",
    )

    state = hass.states.get(THERMOSTAT)
    assert state.state == HVACMode.HEAT
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


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("set_hvac_mode", {"hvac_mode": "off"}),
        ("turn_off", {}),
        ("turn_on", {}),
    ],
)
async def test_thermostat_cannot_be_switched_off(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
    service: str,
    data: dict,
) -> None:
    """Test a single thermostat can not be switched off.

    Heating / cooling / off is set for all thermostats by the hvac mode of the
    controller, a thermostat only switches between comfort and eco.
    """
    with pytest.raises(HomeAssistantError):
        await call_service(hass, "climate", service, THERMOSTAT, **data)

    assert controller.writes == []


async def test_set_hvac_mode_current(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test setting the current hvac mode changes nothing."""
    await call_service(hass, "climate", "set_hvac_mode", THERMOSTAT, hvac_mode="heat")

    assert controller.writes == []


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
    assert state.attributes.get("preset_modes") is None
    assert state.attributes.get("preset_mode") is None


@pytest.mark.parametrize(
    ("values", "state", "action", "preset"),
    [
        ({"hvac_mode": "3"}, "unknown", None, None),
        ({"th00_active": "2"}, HVACMode.HEAT, HVACAction.HEATING, None),
        ({"th00_output": "2"}, HVACMode.HEAT, None, "comfort"),
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
    preset: str | None,
) -> None:
    """Test unexpected values on the controller result in an unknown state."""
    await _set(hass, controller, init_integration, **values)

    thermostat = hass.states.get(THERMOSTAT)
    assert thermostat.state == state
    assert thermostat.attributes.get("hvac_action") == action
    assert thermostat.attributes.get("preset_mode") == preset


async def test_thermostat_non_numeric_humidity(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test a non-numeric humidity is unknown and does not block the state."""
    await _set(
        hass, controller, init_integration, th00_humidity="x", th00_temperature="230"
    )

    thermostat = hass.states.get(THERMOSTAT)
    assert thermostat.attributes["current_temperature"] == 23.0
    assert thermostat.attributes.get("current_humidity") is None


@pytest.mark.parametrize(
    ("hvac_mode", "hvac_modes", "preset_modes"),
    [
        ("0", [HVACMode.OFF], None),
        ("1", [HVACMode.HEAT], ["comfort", "eco"]),
        ("2", [HVACMode.COOL], ["comfort", "eco"]),
    ],
)
async def test_thermostat_modes_match_state_after_setup(
    hass: HomeAssistant,
    controller: FakeController,
    mock_config_entry: MockConfigEntry,
    hvac_mode: str,
    hvac_modes: list[HVACMode],
    preset_modes: list[str] | None,
) -> None:
    """Test the offered modes fit the state already in the first state."""
    controller.values["c1000.hvac_mode"] = hvac_mode
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(THERMOSTAT)
    assert state.attributes["hvac_modes"] == hvac_modes
    assert state.attributes.get("preset_modes") == preset_modes


async def test_comfort_target_without_active_setpoint(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test the comfort setpoint is the target while no setpoint is active."""
    await _set(
        hass,
        controller,
        init_integration,
        th00_setpoint_active="0",
        th00_setpoint="215",
    )

    assert hass.states.get(THERMOSTAT).attributes["temperature"] == 21.5


async def test_set_preset_boost(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test boost runs the fan at max."""
    await _set(hass, controller, init_integration, th00_fan_options="16")

    await call_service(
        hass, "climate", "set_preset_mode", THERMOSTAT, preset_mode="boost"
    )

    assert controller.writes == [(f"{TH}_fan_limit", "4")]
    assert hass.states.get(THERMOSTAT).attributes["preset_mode"] == "boost"


async def test_set_temperature_boost_cooling(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test boost while cooling changes the lower setpoint limit."""
    await _set(
        hass,
        controller,
        init_integration,
        hvac_mode="2",
        th00_fan_options="16",
        th00_fan_limit="4",
    )

    await call_service(hass, "climate", "set_temperature", THERMOSTAT, temperature=18)

    assert controller.writes == [
        (f"{TH}_setpoint_lo", "180"),
        (f"{TH}_config2_req", "1"),
    ]
