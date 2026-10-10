"""Tests for setting up and unloading the HIQ-Home integration."""

from __future__ import annotations

import logging
from typing import TypedDict
from unittest.mock import patch

import pytest
from cybro import CybroConnectionTimeoutError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hiq import get_write_req_th
from custom_components.hiq.const import DOMAIN
from custom_components.hiq.coordinator import HiqDataUpdateCoordinator

from .const import HOST, NAD, OPTIONS, PORT, TITLE
from .fake_controller import HIQ_TAGS, FakeController

LIGHT = "light.lights_light_c1000_lc00_qx00_light"
SERVICES = (
    "presence_signal",
    "charge_on_event",
    "charge_off_event",
    "home_event",
    "alarm_event",
    "precede_event",
    "write_tag",
)


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the entry loads, registers services and cleans up on unload."""
    assert init_integration.state is ConfigEntryState.LOADED
    for service in SERVICES:
        assert hass.services.has_service(DOMAIN, service)

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data
    for service in SERVICES:
        assert not hass.services.has_service(DOMAIN, service)


async def test_setup_retry_when_offline(
    hass: HomeAssistant,
    controller: FakeController,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup is retried when the SCGI server can not be reached."""
    controller.online = False
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retry_when_module_states_unreadable(
    hass: HomeAssistant,
    controller: FakeController,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup is retried when the module states can not be read.

    They are read in a second poll, as they decide which entities are created.
    """
    refresh = HiqDataUpdateCoordinator.async_refresh

    async def _offline_refresh(coordinator: HiqDataUpdateCoordinator) -> None:
        controller.online = False
        await refresh(coordinator)

    mock_config_entry.add_to_hass(hass)
    with patch.object(HiqDataUpdateCoordinator, "async_refresh", _offline_refresh):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_entities_unavailable_on_timeout(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test a timeout of the SCGI server makes the entities unavailable."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id]

    with patch.object(
        coordinator.cybro, "update", side_effect=CybroConnectionTimeoutError
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert hass.states.get(LIGHT).state == STATE_UNAVAILABLE
    assert "Could not connect" in str(coordinator.last_exception)


@pytest.mark.parametrize(
    ("tag", "request_tag"),
    [
        ("fan_options", "config1_req"),
        ("setpoint_idle", "config2_req"),
        ("beep_enable", "config3_req"),
        ("dndmmr_enable", "config4_req"),
        ("setpoint", None),
    ],
)
def test_thermostat_write_request(tag: str, request_tag: str | None) -> None:
    """Test thermostat config tags are written together with their request."""
    expected = request_tag and f"c1000.th00_{request_tag}"
    assert get_write_req_th(f"c1000.th00_{tag}", "c1000.th00") == expected


async def test_entities_unavailable_while_offline(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test entities become unavailable and recover with the controller."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id]
    assert hass.states.get(LIGHT).state == "on"

    controller.online = False
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(LIGHT).state == STATE_UNAVAILABLE

    controller.online = True
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(LIGHT).state == "on"


async def test_migrate_entry_v1(
    hass: HomeAssistant, controller: FakeController
) -> None:
    """Test version 1 entries move the connection from data to options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        title="old title",
        data={"host": HOST, "port": PORT, "address": NAD},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.data == {}
    assert entry.options == OPTIONS
    assert entry.title == TITLE
    assert entry.unique_id == TITLE


async def test_devices_linked_to_controller(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test every device of the entry is linked to the controller device."""
    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(
        device_registry, init_integration.entry_id
    )
    controller = next(d for d in devices if (DOMAIN, NAD) in d.identifiers)
    children = [d for d in devices if d.id != controller.id]

    assert controller.name == f"c{NAD} diagnostic"
    assert controller.via_device_id is None
    assert len(children) >= 5
    assert {d.name: d.via_device_id for d in children} == {
        d.name: controller.id for d in children
    }


async def test_via_device_fallback_for_older_home_assistant(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the controller is linked by identifier if via_device_id is unknown."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id]
    assert coordinator.via_device_info == {"via_device_id": coordinator.device_id}

    class OldDeviceInfo(TypedDict, total=False):
        """DeviceInfo before Home Assistant 2026.8."""

        identifiers: set[tuple[str, str]]

    with patch("custom_components.hiq.coordinator.DeviceInfo", OldDeviceInfo):
        assert coordinator.via_device_info == {"via_device": (DOMAIN, NAD)}


async def test_unload_one_of_two_controllers(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test unloading one controller keeps the other one working."""
    controller.add_controller(1001, HIQ_TAGS)
    second = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title=f"c1001@{HOST}:{PORT}",
        options={**OPTIONS, "address": 1001},
    )
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert second.state is ConfigEntryState.LOADED
    coordinator = hass.data[DOMAIN][second.entry_id]
    await coordinator.async_refresh()
    assert coordinator.last_update_success

    await hass.services.async_call(
        DOMAIN,
        "write_tag",
        {
            "entity_id": ["light.lights_light_c1001_lc00_qx00_light"],
            "tag": "lc00_qx00",
            "value": "0",
        },
        blocking=True,
    )
    assert controller.written("c1001.lc00_qx00") == ["0"]

    assert await hass.config_entries.async_unload(second.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN not in hass.data
    assert not hass.services.has_service(DOMAIN, "write_tag")


async def test_no_warnings_on_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    controller: FakeController,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test setup logs no warnings, e.g. deprecated Home Assistant API usage."""
    caplog.set_level(logging.DEBUG)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    problems = [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.WARNING
        and "has not been tested by Home Assistant" not in record.getMessage()
        # asyncio debug mode reports slow steps, which depends on the runner
        and not (
            record.name == "asyncio" and record.getMessage().startswith("Executing")
        )
    ]
    assert problems == []
