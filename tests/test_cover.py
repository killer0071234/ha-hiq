"""Tests for HIQ-Home blinds."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.hiq.const import DEVICE_SW_VERSION

from .common import call_service, refresh, setup_with_tags
from .fake_controller import FakeController

BLIND = "cover.blinds_blind_c1000_bc00_blinds_position_00_blind"
SETPOINT = "c1000.bc00_blinds_setpoint_00"


async def test_blind_state(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test the position is inverted, the controller counts closing percent."""
    state = hass.states.get(BLIND)
    assert state.state == "open"
    assert state.attributes["current_position"] == 60
    assert state.attributes["device_class"] == "blind"

    controller.values["c1000.bc00_blinds_position_00"] = "100"
    await refresh(hass, init_integration)
    assert hass.states.get(BLIND).state == "closed"
    assert hass.states.get(BLIND).attributes["current_position"] == 0


async def test_blind_unknown_position(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test an unknown position from the controller results in an unknown state."""
    controller.values["c1000.bc00_blinds_position_00"] = "?"
    await refresh(hass, init_integration)

    state = hass.states.get(BLIND)
    assert state.state == "unknown"
    assert state.attributes.get("current_position") is None


@pytest.mark.parametrize(
    ("moving", "expected"),
    [("bc00_qxs00_up", "opening"), ("bc00_qxs00_dn", "closing")],
)
async def test_blind_moving(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
    moving: str,
    expected: str,
) -> None:
    """Test the motor outputs are shown as opening / closing."""
    controller.values[f"c1000.{moving}"] = "1"
    await refresh(hass, init_integration)

    assert hass.states.get(BLIND).state == expected


@pytest.mark.parametrize(
    ("service", "data", "written"),
    [
        ("open_cover", {}, "0"),
        ("close_cover", {}, "100"),
        ("stop_cover", {}, "-1"),
        ("set_cover_position", {"position": 30}, "70"),
    ],
)
async def test_blind_control(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
    service: str,
    data: dict,
    written: str,
) -> None:
    """Test commands are written to the blind setpoint."""
    await call_service(hass, "cover", service, BLIND, **data)

    assert controller.written(SETPOINT) == [written]


def _device(hass: HomeAssistant, entity_id: str) -> dr.DeviceEntry:
    """Return the device of an entity."""
    entry = er.async_get(hass).async_get(entity_id)
    return dr.async_get(hass).async_get(entry.device_id)


async def test_blind_device_shows_module(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a blind device shows the model and firmware of its module."""
    device = _device(hass, BLIND)

    assert (device.model, device.sw_version, device.hw_version) == (
        "BC-5-IQ",
        "1.1.0.2",
        "2/3",
    )


async def test_blind_device_defaults(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a blind without module info keeps the default device info."""
    await setup_with_tags(
        hass,
        aioclient_mock,
        mock_config_entry,
        {"bc00_general_error": "0", "bc00_blinds_position_00": "40"},
    )

    device = _device(hass, BLIND)
    assert device.name == "Blind c1000.bc00_blinds_position_00"
    assert (device.model, device.sw_version, device.hw_version) == (
        "HIQ controller",
        DEVICE_SW_VERSION,
        "2/3",
    )
