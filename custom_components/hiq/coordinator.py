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
from homeassistant.helpers.template import Template
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DEFAULT_HOST
from .const import DOMAIN
from .const import LOGGER
from .const import SCAN_INTERVAL
from .const import SCAN_INTERVAL_ADDON


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

        update_interval = SCAN_INTERVAL
        if entry.data[CONF_HOST] in (
            DEFAULT_HOST,
            "localhost",
            "127.0.0.1",
            "::1",
        ):
            update_interval = SCAN_INTERVAL_ADDON

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> HiqDevice:
        """Fetch data from HIQ Controller."""
        try:
            device = await self.cybro.update(
                full_update=not self.last_update_success, device_type=1
            )
        except CybroConnectionTimeoutError as error:
            raise UpdateFailed(
                f"Could not connect to Cybro scgi server: {error}"
            ) from error
        except CybroError as error:
            raise UpdateFailed(
                f"Invalid response from Cybro scgi server: {error}"
            ) from error

        self.async_update_listeners()

        return device

    def get_value(
        self,
        tag: str,
        factor: float = 1.0,
        precision: int | None = 0,
        def_val: str | int | float | None = None,
    ) -> str | int | float | None:
        """Return a single Tag Value and format it with a specific factor."""
        res = self.data.vars.get(tag, None)
        if res is None:
            return def_val
        if res.value == "?" or res.value is None:
            LOGGER.debug("get_value: %s -> ? (%s)", str(tag), str(def_val))
            return def_val
        try:
            if precision is None:
                LOGGER.debug("get_value: %s -> %s", str(tag), str(res.value))
                return res.value
            # try to parse float value, if fails, try to return int, else return as string
            if factor != 1.0 or precision != 0 or res.value in (",", "."):
                converted_numerical_value = float(res.value.replace(",", "")) * factor
                value = f"{converted_numerical_value:z.{precision}f}"
                LOGGER.debug(
                    "get_value: %s -> %s",
                    str(tag),
                    str(value),
                )
                return float(value)
            LOGGER.debug("get_value: %s -> %s", str(tag), str(res.value))
            return int(res.value)
        except ValueError:
            LOGGER.debug("get_value: %s -> %s", str(tag), str(res.value))
            return res.value

    def get_template_value(
        self,
        tag: str,
        value_template: Template | None = None,
        def_val: bool | str | int | float | None = None,
    ) -> bool | str | int | float | None:
        """Return a single Tag Value and format it with a given template."""
        res = self.data.vars.get(tag, None)
        if res is None:
            return def_val
        if res.value == "?" or res.value is None:
            LOGGER.debug("get_template_value: %s -> ? (%s)", str(tag), str(def_val))
            return def_val
        value = res.value
        if (template := value_template) is not None:
            value = template.async_render_with_possible_json_value(value, None)
        LOGGER.debug("get_template_value: %s -> %s", str(tag), str(value))
        return value
