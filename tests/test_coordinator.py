"""Tests for value conversion of the HIQ-Home coordinator."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hiq.const import DOMAIN
from custom_components.hiq.coordinator import HiqDataUpdateCoordinator

from .fake_controller import FakeController

VAR = "c1000.scan_time"


@pytest.fixture
async def coordinator(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> HiqDataUpdateCoordinator:
    """Return the coordinator with scan_time polled."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id]
    coordinator.data.add_var(VAR)
    await coordinator.async_refresh()
    return coordinator


async def _value(
    coordinator: HiqDataUpdateCoordinator,
    controller: FakeController,
    raw: str,
) -> None:
    controller.values[VAR] = raw
    await coordinator.async_refresh()


@pytest.mark.parametrize(
    ("raw", "factor", "precision", "expected"),
    [
        ("215", 1.0, 0, 215),
        ("215", 0.1, 1, 21.5),
        ("-5", 0.1, 1, -0.5),
        ("1,234", 1.0, 1, 1234.0),
        ("12.4", 1.0, 0, 12.0),
        ("12.6", 1.0, 0, 13.0),
        ("1,234", 1.0, 0, 1234.0),
        ("15787.1826171875", 1.0, 0, 15787.0),
        ("0", 0.1, 1, 0.0),
        ("abc", 1.0, 0, "abc"),
        ("12.5", 1.0, None, "12.5"),
    ],
)
async def test_get_value(
    coordinator: HiqDataUpdateCoordinator,
    controller: FakeController,
    raw: str,
    factor: float,
    precision: int | None,
    expected: object,
) -> None:
    """Test values are scaled, rounded and converted."""
    await _value(coordinator, controller, raw)

    assert coordinator.get_value(VAR, factor, precision) == expected


async def test_get_value_unknown(
    coordinator: HiqDataUpdateCoordinator, controller: FakeController
) -> None:
    """Test unknown or missing values return the default."""
    await _value(coordinator, controller, "?")

    assert coordinator.get_value(VAR, def_val=7) == 7
    assert coordinator.get_value("c1000.not_polled", def_val=8) == 8


async def test_get_template_value(
    hass: HomeAssistant,
    coordinator: HiqDataUpdateCoordinator,
    controller: FakeController,
) -> None:
    """Test values are rendered with a template."""
    await _value(coordinator, controller, "21")

    assert coordinator.get_template_value(VAR) == "21"
    assert (
        coordinator.get_template_value(VAR, Template("{{ value | int + 1 }}", hass))
        == "22"
    )

    await _value(coordinator, controller, "?")
    assert coordinator.get_template_value(VAR, def_val="x") == "x"


async def test_listeners_updated_once_with_new_data(
    coordinator: HiqDataUpdateCoordinator, controller: FakeController
) -> None:
    """Test a poll notifies the entities once, with the new values."""
    seen: list[object] = []
    unsub = coordinator.async_add_listener(
        lambda: seen.append(coordinator.get_value(VAR))
    )

    await _value(coordinator, controller, "42")
    unsub()

    assert seen == [42]
