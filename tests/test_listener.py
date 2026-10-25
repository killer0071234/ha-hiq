"""Tests for the frames controllers send on their own (sockets, push)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from cybro.abus.frame import Command, Frame
from cybro.testing import FakeAbusController
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hiq.const import DOMAIN
from custom_components.hiq.transport import async_current_transport

from .const import NAD, OPTIONS
from .fake_abus import direct_entry, start_hiq_controller


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _received(hass: HomeAssistant, count: int) -> None:
    """Wait until the shared socket received count more frames."""
    transport = async_current_transport(hass)
    target = transport.rx_count + count
    async with asyncio.timeout(1):
        while transport.rx_count < target:
            await asyncio.sleep(0.01)
    await hass.async_block_till_done()


async def _send(
    hass: HomeAssistant, sender: FakeAbusController, send: Callable[[], None]
) -> None:
    send()
    await _received(hass, 1)


async def test_static_ip_updated(
    hass: HomeAssistant, abus_controller: FakeAbusController
) -> None:
    """Test a socket frame fixes the static IP of an entry that can't connect."""
    await _setup(hass, direct_entry())
    moved = await start_hiq_controller(
        NAD + 1, host="127.0.0.2", port=abus_controller.port
    )
    entry = direct_entry(NAD + 1, ip_address="127.0.0.9")
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    addr = async_current_transport(hass).local_addr

    await _send(hass, moved, lambda: moved.send_socket(addr, 3, b"\x01"))

    assert entry.options["ip_address"] == "127.0.0.2"
    moved.close()


async def test_learned_ip_updated(
    hass: HomeAssistant, abus_controller: FakeAbusController
) -> None:
    """Test an entry without static IP takes the new IP right away."""
    entry = direct_entry(ip_address=None)
    await _setup(hass, entry)
    client = hass.data[DOMAIN][entry.entry_id].cybro.client
    assert client.ip == "127.0.0.1"
    moved = await start_hiq_controller(NAD, host="127.0.0.2", port=0)
    addr = async_current_transport(hass).local_addr

    await _send(hass, moved, lambda: moved.send_push(addr))

    assert client.ip == "127.0.0.2"
    assert entry.options == {"address": NAD, "connection": "direct"}
    moved.close()


async def test_other_frames_ignored(
    hass: HomeAssistant, abus_controller: FakeAbusController
) -> None:
    """Test unknown NADs, scgi entries and requests of other masters change nothing."""
    entry = direct_entry()
    await _setup(hass, entry)
    scgi = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id="c2000",
        options={**OPTIONS, "address": 2000},
    )
    scgi.add_to_hass(hass)
    sender = await start_hiq_controller(2000, host="127.0.0.2", port=0)
    addr = async_current_transport(hass).local_addr

    # a device that sends sockets but doesn't answer (c13049898)
    sender.nad = 13049898
    await _send(hass, sender, lambda: sender.send_socket(addr, 24))
    # an scgi entry is reached through the scgi server
    sender.nad = 2000
    await _send(hass, sender, lambda: sender.send_socket(addr, 4))
    # an scgi server (source NAD 1003) searching the controller
    await _send(
        hass,
        sender,
        lambda: sender.send_frame(Frame.request(1003, NAD, 1, Command.PING), addr),
    )

    assert entry.options["ip_address"] == "127.0.0.1"
    assert scgi.options == {**OPTIONS, "address": 2000}
    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN) == []
    sender.close()
