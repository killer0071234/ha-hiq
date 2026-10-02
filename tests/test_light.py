"""Tests for HIQ-Home lights."""

from __future__ import annotations

import pytest
from homeassistant.components.light import ColorMode
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .common import call_service, refresh
from .fake_controller import FakeController

ONOFF = "light.lights_light_c1000_lc00_qx00_light"
DIMMER = "light.lights_light_c1000_ld01_qw00_light"
RGB = "light.lights_light_c1000_ld00_qw00_light"


async def test_lights_found(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test lights are created only for modules without a general error."""
    assert sorted(hass.states.async_entity_ids("light")) == sorted([ONOFF, DIMMER, RGB])


async def test_onoff_light(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test a switched light output."""
    state = hass.states.get(ONOFF)
    assert state.state == "on"
    assert state.attributes["color_mode"] == ColorMode.ONOFF
    assert state.attributes["supported_color_modes"] == [ColorMode.ONOFF]
    assert state.attributes["variable"] == "c1000.lc00_qx00"
    assert state.attributes["description"] == "Description of c1000.lc00_qx00"

    await call_service(hass, "light", "turn_off", ONOFF)
    assert controller.written("c1000.lc00_qx00") == ["0"]
    assert hass.states.get(ONOFF).state == "off"

    await call_service(hass, "light", "turn_on", ONOFF)
    assert controller.written("c1000.lc00_qx00") == ["0", "1"]
    assert hass.states.get(ONOFF).state == "on"


async def test_dimmable_light(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test a dimmer output, brightness is a percentage on the controller."""
    state = hass.states.get(DIMMER)
    assert state.state == "on"
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["brightness"] == 102  # 40 %

    await call_service(hass, "light", "turn_on", DIMMER)
    assert controller.written("c1000.ld01_qw00") == ["100"]

    await call_service(hass, "light", "turn_off", DIMMER)
    assert controller.written("c1000.ld01_qw00")[-1] == "0"
    assert hass.states.get(DIMMER).state == "off"


@pytest.mark.parametrize(
    ("brightness", "percent"),
    [(255, "100"), (128, "50"), (64, "25"), (3, "1"), (1, "1")],
)
async def test_dimmable_light_brightness(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
    brightness: int,
    percent: str,
) -> None:
    """Test brightness is written as whole percent, never 0 when turning on."""
    await call_service(hass, "light", "turn_on", DIMMER, brightness=brightness)

    assert controller.written("c1000.ld01_qw00") == [percent]
    assert hass.states.get(DIMMER).state == "on"


async def test_rgb_light(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test an rgb light, hue is stored as 0..100 on the controller."""
    state = hass.states.get(RGB)
    assert state.attributes["color_mode"] == ColorMode.HS
    assert state.attributes["supported_color_modes"] == [ColorMode.HS]
    assert state.attributes["brightness"] == 127

    await call_service(hass, "light", "turn_on", RGB, hs_color=(120, 50))

    assert controller.written("c1000.ld00_qw01") == ["33"]
    assert controller.written("c1000.ld00_qw02") == ["50"]
    assert controller.written("c1000.ld00_qw00") == []


async def test_light_state_changes_on_controller(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test changes made on the controller are picked up by polling."""
    controller.values["c1000.lc00_qx00"] = "0"
    controller.values["c1000.ld01_qw00"] = "0"
    await refresh(hass, init_integration)

    assert hass.states.get(ONOFF).state == "off"
    assert hass.states.get(DIMMER).state == "off"


async def test_dimmable_light_full_brightness(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test 100 % on the controller is reported as full brightness."""
    controller.values["c1000.ld01_qw00"] = "100"
    await refresh(hass, init_integration)

    assert hass.states.get(DIMMER).attributes["brightness"] == 255


async def test_rgb_light_reports_color(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the color of an rgb light is read from the controller."""
    assert tuple(hass.states.get(RGB).attributes["hs_color"]) == (180, 80)
