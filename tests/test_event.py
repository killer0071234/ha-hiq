"""Tests for socket 1 of the HIQ program: button events and faster states."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import patch

import pytest
from cybro.abus import encode_socket_values
from cybro.testing import FakeAbusController
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed_exact,
)

from custom_components.hiq.const import DOMAIN
from custom_components.hiq.event import input_number
from custom_components.hiq.transport import async_current_transport

from .const import NAD
from .fake_abus import SOCKET_VARS, TRANSPORT, direct_entry, start_hiq_controller
from .fake_controller import HIQ_TAGS
from .test_direct import LIGHT, setup_entry

# lc01 has a general error
INPUTS = {"lc00_ix03": "0", "lc01_ix00": "0", "ld01_ix03": "0"}


@pytest.fixture
async def socket_controller(
    socket_enabled: None,
) -> AsyncGenerator[FakeAbusController]:
    """Return a controller whose program has socket 1 and button inputs."""
    fake = await start_hiq_controller(NAD, HIQ_TAGS | INPUTS, extra=SOCKET_VARS)
    with (
        patch(f"{TRANSPORT}.BIND_HOST", "127.0.0.1"),
        patch(f"{TRANSPORT}.LOCAL_PORT", 0),
        patch(f"{TRANSPORT}.CONTROLLER_PORT", fake.port),
        patch(f"{TRANSPORT}.BROADCAST", "127.0.0.1"),
    ):
        yield fake
    fake.close()


async def send(
    hass: HomeAssistant,
    sender: FakeAbusController,
    command: int,
    argument_0: int = 0,
    argument_1: int = 0,
    *,
    req: int = 1,
    from_nad: int | None = None,
) -> None:
    """Send a socket 1 message and wait until it is handled."""
    body = encode_socket_values(
        bits=[req],
        ints=[command, argument_0, argument_1, 0, 0],
        longs=[sender.nad if from_nad is None else from_nad, 0],
    )
    assert len(body) == 19
    transport = async_current_transport(hass)
    target = transport.rx_count + 1
    sender.send_socket(transport.local_addr, 1, body)
    async with asyncio.timeout(1):
        while transport.rx_count < target:
            await asyncio.sleep(0.01)
    await hass.async_block_till_done()


def event_entity(hass: HomeAssistant, var: str) -> str | None:
    """Return the entity id of the button input of a variable."""
    return er.async_get(hass).async_get_entity_id(
        "event", DOMAIN, f"c{NAD}.{var}_event"
    )


async def test_button_events(
    hass: HomeAssistant,
    socket_controller: FakeAbusController,
    enable_all_entities: None,
) -> None:
    """Test input events of LC and LD modules fire on their event entity."""
    await setup_entry(hass, direct_entry())
    lc_input = event_entity(hass, "lc00_ix03")
    ld_input = event_entity(hass, "ld01_ix03")
    assert lc_input == "event.lights_inputs_c1000_lc00_input_ix03"
    assert hass.states.get(lc_input).state == STATE_UNKNOWN

    await send(hass, socket_controller, 0, 3, 2)

    state = hass.states.get(lc_input)
    assert state.attributes["event_type"] == "long_press"
    assert state.attributes["event_types"] == [
        "short_press",
        "short_release",
        "long_press",
        "long_release",
    ]
    assert state.attributes["device_class"] == "button"
    assert hass.states.get(ld_input).state == STATE_UNKNOWN

    # socket_req only makes the program send the socket, it is not checked
    await send(hass, socket_controller, 0, 113, 1, req=0)

    assert hass.states.get(ld_input).attributes["event_type"] == "short_release"


async def test_ignored_messages(
    hass: HomeAssistant,
    socket_controller: FakeAbusController,
    enable_all_entities: None,
) -> None:
    """Test messages that are no input event of this controller fire nothing."""
    await setup_entry(hass, direct_entry())
    lc_input = event_entity(hass, "lc00_ix03")

    # message of another controller in the socket
    await send(hass, socket_controller, 0, 3, 0, from_nad=NAD + 1)
    # unknown event type, input without entity, another command
    await send(hass, socket_controller, 0, 3, 4)
    await send(hass, socket_controller, 0, 4, 0)
    await send(hass, socket_controller, 4, 3, 1)
    # another controller sends socket 1
    other = await start_hiq_controller(NAD + 1, extra=SOCKET_VARS)
    await send(hass, other, 0, 3, 0)
    other.close()

    assert hass.states.get(lc_input).state == STATE_UNKNOWN


async def test_entities(
    hass: HomeAssistant, socket_controller: FakeAbusController
) -> None:
    """Test inputs of working modules only, disabled by default."""
    await setup_entry(hass, direct_entry())

    entry = er.async_get(hass).async_get(event_entity(hass, "lc00_ix03"))
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert event_entity(hass, "ld01_ix03") is not None
    assert event_entity(hass, "lc01_ix00") is None


async def test_refresh_after_a_second(
    hass: HomeAssistant, socket_controller: FakeAbusController
) -> None:
    """Test socket messages refresh the values once, not before a second."""
    entry = direct_entry()
    await setup_entry(hass, entry)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert hass.states.get(LIGHT).state == "on"
    socket_controller["lc00_qx00"] = 0

    with patch.object(
        coordinator.cybro, "update", wraps=coordinator.cybro.update
    ) as update:
        await send(hass, socket_controller, 4, 3, 1)
        await send(hass, socket_controller, 0, 3, 0)
        async_fire_time_changed_exact(hass, dt_util.utcnow() + timedelta(seconds=0.5))
        await hass.async_block_till_done()
        assert hass.states.get(LIGHT).state == "on"

        async_fire_time_changed_exact(hass, dt_util.utcnow() + timedelta(seconds=1.1))
        await hass.async_block_till_done()

    assert update.call_count == 1
    assert hass.states.get(LIGHT).state == "off"


async def test_no_socket(
    hass: HomeAssistant, abus_controller: FakeAbusController
) -> None:
    """Test a program without socket 1 variables gets no socket and no events."""
    entry = direct_entry()
    await setup_entry(hass, entry)

    assert not hass.data[DOMAIN][entry.entry_id].has_socket
    assert not hass.states.async_entity_ids("event")


async def test_scgi_no_socket(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test entries using the scgi server get no socket and no events."""
    assert not hass.data[DOMAIN][init_integration.entry_id].has_socket
    assert not hass.states.async_entity_ids("event")


async def test_reload_removes_handler(
    hass: HomeAssistant, socket_controller: FakeAbusController
) -> None:
    """Test an unloaded entry leaves no socket handler on the shared transport."""
    # the second controller keeps the transport open
    second_controller = await start_hiq_controller(
        NAD + 1, host="127.0.0.2", port=socket_controller.port
    )
    await setup_entry(hass, direct_entry(NAD + 1, ip_address="127.0.0.2"))
    callbacks = async_current_transport(hass)._callbacks
    count = len(callbacks)
    entry = direct_entry()
    await setup_entry(hass, entry)
    assert len(callbacks) == count + 1

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert async_current_transport(hass)._callbacks is callbacks
    assert len(callbacks) == count + 1
    assert hass.data[DOMAIN][entry.entry_id].has_socket
    second_controller.close()


@pytest.mark.parametrize(
    ("key", "number"),
    [
        ("c1000.lc00_ix00", 0),
        ("c1000.lc07_ix09", 79),
        ("c1000.ld00_ix00", 100),
        ("c1000.ld03_ix09", 139),
        ("c1000.lc08_ix00", None),
        ("c1000.ld04_ix00", None),
        ("c1000.lc00_ix10", None),
        ("c1000.lc00_qx00", None),
        ("c1000.th00_ix00", None),
    ],
)
def test_input_number(key: str, number: int | None) -> None:
    """Test the input numbers of the program."""
    assert input_number(key) == number
