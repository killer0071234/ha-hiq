"""A-bus (UDP) socket shared by all directly connected controllers."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from cybro.abus import ABUS_PORT, AbusTransport
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, ISSUE_PORT_IN_USE, LOGGER

# controllers send push and socket frames to this port of Home Assistant
BIND_HOST = "0.0.0.0"  # noqa: S104
LOCAL_PORT = ABUS_PORT
# port of the controllers, and where controllers without IP are searched
CONTROLLER_PORT = ABUS_PORT
BROADCAST = "255.255.255.255"


@dataclass
class SharedTransport:
    """The socket and the entries using it."""

    transport: AbusTransport | None = None
    entries: set[str] = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


DATA_TRANSPORT: HassKey[SharedTransport] = HassKey(f"{DOMAIN}_transport")


async def async_get_transport(hass: HomeAssistant, entry_id: str) -> AbusTransport:
    """Return the shared socket, open it for the first entry."""
    shared = hass.data.setdefault(DATA_TRANSPORT, SharedTransport())
    async with shared.lock:
        if shared.transport is None:
            shared.transport = await _async_create(hass)
        shared.entries.add(entry_id)
        return shared.transport


def async_current_transport(hass: HomeAssistant) -> AbusTransport | None:
    """Return the open shared socket, if any."""
    shared = hass.data.get(DATA_TRANSPORT)
    return None if shared is None else shared.transport


def async_release_transport(hass: HomeAssistant, entry_id: str) -> None:
    """Stop using the shared socket, close it after the last entry."""
    shared = hass.data[DATA_TRANSPORT]
    shared.entries.discard(entry_id)
    # the holder (and its lock) stays, an entry may be waiting for the lock
    if not shared.entries and shared.transport is not None:
        shared.transport.close()
        shared.transport = None


@asynccontextmanager
async def async_scan_transport(hass: HomeAssistant) -> AsyncIterator[AbusTransport]:
    """Use the shared socket, or one on any port while no entry has it open.

    Answers come back to the sending port, so a scan doesn't need port 8442.
    Binding it here would also report the scgi app as a port conflict to
    users who only use the scgi server.
    """
    if (transport := async_current_transport(hass)) is not None:
        yield transport
        return
    transport = await AbusTransport.create(
        (BIND_HOST, 0), broadcast=BROADCAST, port=CONTROLLER_PORT
    )
    try:
        yield transport
    finally:
        transport.close()


async def _async_create(hass: HomeAssistant) -> AbusTransport:
    """Open the socket on the A-bus port, on any port if it is in use."""
    options = {"broadcast": BROADCAST, "port": CONTROLLER_PORT}
    try:
        transport = await AbusTransport.create((BIND_HOST, LOCAL_PORT), **options)
    except OSError as err:
        # eg: the CybroScgiServer add-on runs on the same host
        LOGGER.warning(
            "UDP port %s is in use (%s), controllers can't send to Home Assistant",
            LOCAL_PORT,
            err,
        )
        ir.async_create_issue(
            hass,
            DOMAIN,
            ISSUE_PORT_IN_USE,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_PORT_IN_USE,
            translation_placeholders={"port": str(LOCAL_PORT)},
        )
        return await AbusTransport.create((BIND_HOST, 0), **options)
    ir.async_delete_issue(hass, DOMAIN, ISSUE_PORT_IN_USE)
    return transport
