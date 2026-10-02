"""Tests for the HIQ-Home services."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hiq.const import DOMAIN

from .fake_controller import FakeController

LIGHT = "light.lights_light_c1000_lc00_qx00_light"


@pytest.mark.parametrize(
    ("service", "tag"),
    [
        ("presence_signal", "smartphone_presence_signal"),
        ("charge_on_event", "smartphone_charge_on_event"),
        ("charge_off_event", "smartphone_charge_off_event"),
        ("home_event", "smartphone_home_event"),
        ("alarm_event", "smartphone_alarm_event"),
    ],
)
async def test_smartphone_events(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
    service: str,
    tag: str,
) -> None:
    """Test smartphone events set their trigger on the targeted controller."""
    await hass.services.async_call(
        DOMAIN, service, {"entity_id": [LIGHT]}, blocking=True
    )

    assert controller.writes == [(f"c1000.{tag}", "1")]


async def test_precede_event(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test the precede minutes are written before the event trigger."""
    await hass.services.async_call(
        DOMAIN, "precede_event", {"entity_id": [LIGHT], "time": 15}, blocking=True
    )

    assert controller.writes == [
        ("c1000.smartphone_precede_minutes", "15"),
        ("c1000.smartphone_precede_event", "1"),
    ]


async def test_write_tag_by_device(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test a device target resolves to the controller of its config entry."""
    device_id = er.async_get(hass).async_get(LIGHT).device_id

    await hass.services.async_call(
        DOMAIN,
        "write_tag",
        {"device_id": [device_id], "tag": "lc00_qx00", "value": "0"},
        blocking=True,
    )

    assert controller.writes == [("c1000.lc00_qx00", "0")]


async def test_write_tag_without_target(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test nothing is written without a target."""
    await hass.services.async_call(
        DOMAIN, "write_tag", {"tag": "lc00_qx00", "value": "0"}, blocking=True
    )

    assert controller.writes == []


@pytest.mark.xfail(
    reason="services have no schema, a single entity_id string is iterated "
    "character by character",
    strict=True,
)
async def test_service_single_entity_id(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test a single entity id (as used in YAML) is accepted."""
    await hass.services.async_call(
        DOMAIN, "home_event", {"entity_id": LIGHT}, blocking=True
    )

    assert controller.writes == [("c1000.smartphone_home_event", "1")]
