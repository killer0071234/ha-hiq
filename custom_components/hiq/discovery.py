"""Find HIQ controllers on the LAN by A-bus broadcast and offer them.

Every controller answers a broadcast READ_STATUS to NAD 0 with its own NAD
(docs/abus-notes.md, S2). Only the integration's own scan creates flows:
devices that send sockets but don't answer requests are never offered.
"""

from __future__ import annotations

from typing import Any

from cybro import CybroDirect
from cybro import CybroError
from cybro.abus import AbusTransport
from cybro.abus import ScanResult
from cybro.abus import scan
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import CONF_ADDRESS
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN
from .const import HIQ_PROGRAM_ID
from .const import LOGGER
from .const import SCAN_INTERVAL_DISCOVERY
from .listener import async_ip_seen
from .transport import async_retry_port
from .transport import async_scan_transport

CONF_VERSION = "version"

# variables of the HIQ program, read before a controller is offered
PROGRAM_VARS = ("program_id", "version_major", "version_minor", "version_release")


@callback
def async_setup_discovery(hass: HomeAssistant) -> None:
    """Scan after Home Assistant started, then periodically."""
    # NAD -> HIQ program version, None: no HIQ program (checked once per run)
    checked: dict[int, str | None] = {}

    @callback
    def _async_scan(*_: object) -> None:
        hass.async_create_background_task(
            async_discover(hass, checked), "hiq discovery scan"
        )

    async_at_started(hass, _async_scan)
    async_track_time_interval(
        hass, _async_scan, SCAN_INTERVAL_DISCOVERY, cancel_on_shutdown=True
    )


async def async_discover(hass: HomeAssistant, checked: dict[int, str | None]) -> None:
    """Scan once, offer new HIQ controllers and update the IP of known ones."""
    try:
        await async_retry_port(hass)
        async with async_scan_transport(hass) as transport:
            for result in await scan(transport):
                await _async_found(hass, transport, result, checked)
    except (CybroError, OSError) as err:
        LOGGER.debug("Controller scan failed: %s", err)


async def _async_found(
    hass: HomeAssistant,
    transport: AbusTransport,
    result: ScanResult,
    checked: dict[int, str | None],
) -> None:
    """Handle a controller that answered the scan."""
    if async_ip_seen(hass, result.nad, result.ip):
        return
    if data := await async_discovery_data(hass, transport, result, checked):
        discovery_flow.async_create_flow(
            hass, DOMAIN, context={"source": SOURCE_INTEGRATION_DISCOVERY}, data=data
        )


async def async_discovery_data(
    hass: HomeAssistant,
    transport: AbusTransport,
    result: ScanResult,
    checked: dict[int, str | None],
) -> dict[str, Any] | None:
    """Return the flow data of a controller that isn't connected directly.

    An scgi entry of the controller is offered the direct connection. Other
    controllers are only offered if they run the HIQ program, else None.
    """
    nad, ip = result.nad, result.ip
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN, include_ignore=False)
        if entry.options.get(CONF_ADDRESS) == nad
    ]
    data = {CONF_ADDRESS: nad, CONF_IP_ADDRESS: ip}
    if not entries:
        # variables can only be read from a running program
        if not result.status.ok:
            return None
        if nad not in checked:
            try:
                checked[nad] = await _async_hiq_version(transport, nad, ip)
            except CybroError as err:
                LOGGER.debug("Can't read the program of c%s: %s", nad, err)
                return None
        if checked[nad] is None:
            return None
        data[CONF_VERSION] = checked[nad]
    return data


async def _async_hiq_version(transport: AbusTransport, nad: int, ip: str) -> str | None:
    """Return the HIQ program version, None if the controller runs another one."""
    prefix = f"c{nad}."
    response = await CybroDirect(transport, nad, ip=ip).request(
        {prefix + name: "" for name in PROGRAM_VARS}
    )
    values = {var["name"].removeprefix(prefix): var["value"] for var in response["var"]}
    if values["program_id"] != HIQ_PROGRAM_ID:
        LOGGER.debug("c%s runs no HIQ program, not offered", nad)
        return None
    return ".".join(values[name] for name in PROGRAM_VARS[1:])
