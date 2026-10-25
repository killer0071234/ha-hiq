"""Keep the IP of directly connected controllers up to date.

Controllers send socket (and push) frames to port 8442 on their own
(docs/abus-notes.md, S3). These frames only update configured entries and
never create flows: devices that send sockets but don't answer requests
must not be offered.
"""

from __future__ import annotations

from cybro.abus.frame import Direction
from cybro.abus.frame import Frame
from homeassistant.const import CONF_ADDRESS
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.core import callback

from .const import CONF_CONNECTION
from .const import CONNECTION_DIRECT
from .const import DOMAIN
from .const import LOGGER


@callback
def async_ip_seen(hass: HomeAssistant, nad: int, ip: str) -> bool:
    """Update the direct entries of a controller, False if there are none."""
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN, include_ignore=False)
        if entry.options.get(CONF_ADDRESS) == nad
        and entry.options.get(CONF_CONNECTION) == CONNECTION_DIRECT
    ]
    for entry in entries:
        if (static_ip := entry.options.get(CONF_IP_ADDRESS)) is None:
            # found by broadcast: the loaded entry uses the new IP right away
            coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
            if coordinator is not None:
                coordinator.cybro.client.ip = ip
        elif static_ip != ip:
            # also fixes an entry that can't be set up with the old IP
            LOGGER.info("Controller c%s has the new IP address %s", nad, ip)
            hass.config_entries.async_update_entry(
                entry, options={**entry.options, CONF_IP_ADDRESS: ip}
            )
    return bool(entries)


@callback
def async_frame_received(hass: HomeAssistant, frame: Frame, addr: tuple) -> None:
    """Handle a frame that answers no request of the integration."""
    # push, socket and broadcast frames; requests of other A-bus masters (scgi
    # servers) and their answers don't tell where the controller is
    if frame.to_nad == 0 and frame.direction == Direction.ACK:
        if async_ip_seen(hass, frame.from_nad, addr[0]):
            LOGGER.debug("c%s sent a %s from %s", frame.from_nad, frame.kind, addr[0])
