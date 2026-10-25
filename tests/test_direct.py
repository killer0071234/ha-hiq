"""Tests for the direct A-bus (UDP) connection, without scgi server."""

from __future__ import annotations

import socket
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import pytest
from cybro import CybroDirect
from cybro.testing import FakeAbusController
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hiq.const import DOMAIN, ISSUE_PORT_IN_USE, SCAN_INTERVAL_DIRECT
from custom_components.hiq.transport import async_current_transport

from .common import call_service, refresh
from .const import NAD
from .fake_abus import start_hiq_controller

LIGHT = "light.lights_light_c1000_lc00_qx00_light"
TRANSPORT = "custom_components.hiq.transport"


@pytest.fixture
async def abus_controller(
    socket_enabled: None,
) -> AsyncGenerator[FakeAbusController]:
    """Return a HIQ controller on a fake A-bus, reached via 127.0.0.1."""
    fake = await start_hiq_controller(NAD)
    with (
        patch(f"{TRANSPORT}.BIND_HOST", "127.0.0.1"),
        patch(f"{TRANSPORT}.LOCAL_PORT", 0),
        patch(f"{TRANSPORT}.CONTROLLER_PORT", fake.port),
        patch(f"{TRANSPORT}.BROADCAST", "127.0.0.1"),
    ):
        yield fake
    fake.close()


def direct_entry(nad: int = NAD, **options: Any) -> MockConfigEntry:
    """Return a config entry of a directly connected controller."""
    options = {
        "address": nad,
        "connection": "direct",
        "ip_address": "127.0.0.1",
        **options,
    }
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        title=f"c{nad}",
        unique_id=f"c{nad}",
        options={key: value for key, value in options.items() if value is not None},
    )


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up an entry and read the variables of its entities."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await refresh(hass, entry)


async def test_setup(
    hass: HomeAssistant,
    abus_controller: FakeAbusController,
    enable_all_entities: None,
) -> None:
    """Test a controller is read directly, values formatted like the scgi server."""
    entry = direct_entry()
    await setup_entry(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert isinstance(coordinator.cybro, CybroDirect)
    assert coordinator.update_interval == SCAN_INTERVAL_DIRECT
    assert hass.states.get(LIGHT).state == "on"
    values = coordinator.data.vars
    assert values[f"c{NAD}.power_meter_energy_real"].value == "15787.171875"
    assert values[f"c{NAD}.sys.ip_port"].value == f"127.0.0.1:{abus_controller.port}"


async def test_write(hass: HomeAssistant, abus_controller: FakeAbusController) -> None:
    """Test entities write to the controller."""
    await setup_entry(hass, direct_entry())

    await call_service(hass, "light", "turn_off", LIGHT)

    assert abus_controller["lc00_qx00"] == 0
    assert hass.states.get(LIGHT).state == "off"


async def test_setup_without_ip(
    hass: HomeAssistant, abus_controller: FakeAbusController
) -> None:
    """Test a controller without IP is found by broadcast."""
    entry = direct_entry(ip_address=None)
    await setup_entry(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.data[DOMAIN][entry.entry_id].cybro.client.ip == "127.0.0.1"


async def test_setup_retry_releases_transport(
    hass: HomeAssistant, abus_controller: FakeAbusController
) -> None:
    """Test a controller that doesn't answer is retried, the socket is closed."""
    abus_controller.silent = True
    entry = direct_entry()
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert async_current_transport(hass) is None


async def test_unavailable_on_timeout(
    hass: HomeAssistant, abus_controller: FakeAbusController
) -> None:
    """Test entities are unavailable while the controller doesn't answer."""
    entry = direct_entry()
    await setup_entry(hass, entry)

    abus_controller.silent = True
    await refresh(hass, entry)

    assert hass.states.get(LIGHT).state == STATE_UNAVAILABLE
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert "Could not connect" in str(coordinator.last_exception)

    abus_controller.silent = False
    await refresh(hass, entry)
    assert hass.states.get(LIGHT).state == "on"


async def test_controllers_share_one_transport(
    hass: HomeAssistant, abus_controller: FakeAbusController
) -> None:
    """Test all controllers use one socket, closed with the last entry."""
    second_controller = await start_hiq_controller(
        1001, host="127.0.0.2", port=abus_controller.port
    )
    first = direct_entry()
    second = direct_entry(1001, ip_address="127.0.0.2")
    first.add_to_hass(hass)
    second.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert first.state is ConfigEntryState.LOADED
    assert second.state is ConfigEntryState.LOADED
    transport = hass.data[DOMAIN][first.entry_id].cybro.transport
    assert hass.data[DOMAIN][second.entry_id].cybro.transport is transport

    with patch.object(transport, "close", wraps=transport.close) as close:
        assert await hass.config_entries.async_unload(first.entry_id)
        await refresh(hass, second)
        assert second.state is ConfigEntryState.LOADED
        assert hass.data[DOMAIN][second.entry_id].last_update_success
        close.assert_not_called()

        assert await hass.config_entries.async_unload(second.entry_id)
        close.assert_called_once()
    assert async_current_transport(hass) is None
    second_controller.close()


async def test_port_in_use(
    hass: HomeAssistant, abus_controller: FakeAbusController
) -> None:
    """Test a busy A-bus port falls back to any port and creates a repair issue."""
    busy = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    busy.bind(("127.0.0.1", 0))
    port = busy.getsockname()[1]
    entry = direct_entry()

    with patch(f"{TRANSPORT}.LOCAL_PORT", port):
        await setup_entry(hass, entry)

        assert entry.state is ConfigEntryState.LOADED
        assert hass.states.get(LIGHT).state == "on"
        transport = hass.data[DOMAIN][entry.entry_id].cybro.transport
        assert transport.local_addr[1] != port
        issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_PORT_IN_USE)
        assert issue is not None
        assert issue.translation_placeholders == {"port": str(port)}

        busy.close()
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_PORT_IN_USE) is None


async def test_scgi_entry_has_no_transport(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test entries using the scgi server don't open an A-bus socket."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert async_current_transport(hass) is None
