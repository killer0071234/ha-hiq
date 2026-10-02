"""Tests for HIQ-Home blinds."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .common import call_service, refresh
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
