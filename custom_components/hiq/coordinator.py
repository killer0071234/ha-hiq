"""DataUpdateCoordinator for HIQ-Home."""
from __future__ import annotations

from collections.abc import Callable

from cybro import Cybro
from cybro import CybroConnectionTimeoutError
from cybro import CybroError
from cybro import Device as HiqDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN
from .const import LOGGER
from .const import SCAN_INTERVAL
from .src.app import start_server
from .src.app import stop_server


class HiqDataUpdateCoordinator(DataUpdateCoordinator[HiqDevice]):
    """Class to manage fetching HIQ-Home device data from scgi server."""

    config_entry: ConfigEntry
    unique_id: str

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry: ConfigEntry,
    ) -> None:
        """Initialize global HIQ-Home data updater."""
        self.cybro = Cybro(
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data[CONF_ADDRESS],
            session=async_get_clientsession(hass),
        )
        self.unique_id = "c" + str(entry.data[CONF_ADDRESS])
        self.unsub: Callable | None = None

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> HiqDevice:
        """Fetch data from HIQ Controller."""
        try:
            kill_communication_loop = start_server()

            device = await self.cybro.update(
                full_update=not self.last_update_success, device_type=1
            )

            stop_server(kill_communication_loop)
        except CybroError as error:
            raise UpdateFailed(
                f"Invalid response from Cybro scgi server: {error}"
            ) from error
        except CybroConnectionTimeoutError as error:
            raise UpdateFailed(
                f"Could not connect to Cybro scgi server: {error}"
            ) from error

        self.async_update_listeners()

        return device
