"""DataUpdateCoordinator for HIQ-Home."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from cybro import Cybro
from cybro import CybroDirect
from cybro import CybroConnectionTimeoutError
from cybro import CybroError
from cybro import Device as HiqDevice
from cybro import VarType
from cybro.abus import AbusTransport
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.const import CONF_PASSWORD
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.template import Template
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import CONF_CONNECTION
from .const import CONNECTION_DIRECT
from .const import DEFAULT_HOST
from .const import DOMAIN
from .const import LOGGER
from .const import SCAN_INTERVAL
from .const import SCAN_INTERVAL_ADDON
from .const import SCAN_INTERVAL_DIRECT


class HiqDataUpdateCoordinator(DataUpdateCoordinator[HiqDevice]):
    """Class to manage fetching HIQ-Home device data (scgi server or direct)."""

    config_entry: ConfigEntry
    unique_id: str

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry: ConfigEntry,
        transport: AbusTransport | None = None,
    ) -> None:
        """Initialize global HIQ-Home data updater.

        A directly connected controller (no scgi server) needs the transport.
        """
        options = entry.options
        if options.get(CONF_CONNECTION) == CONNECTION_DIRECT:
            self.cybro: Cybro = CybroDirect(
                transport,
                options[CONF_ADDRESS],
                ip=options.get(CONF_IP_ADDRESS),
                password=options.get(CONF_PASSWORD),
            )
            self._target = f"controller c{options[CONF_ADDRESS]}"
            update_interval = SCAN_INTERVAL_DIRECT
        else:
            self.cybro = Cybro(
                options[CONF_HOST],
                options[CONF_PORT],
                options[CONF_ADDRESS],
                session=async_get_clientsession(hass),
            )
            self._target = "Cybro scgi server"
            is_local = options[CONF_HOST] in (
                DEFAULT_HOST,
                "localhost",
                "127.0.0.1",
                "::1",
            )
            update_interval = SCAN_INTERVAL_ADDON if is_local else SCAN_INTERVAL
        self.unique_id = "c" + str(options[CONF_ADDRESS])
        self.unsub: Callable | None = None
        self.device_id: str | None = None
        # number of entities polling a variable
        self._var_users: dict[str, int] = {}

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
                f"Could not connect to {self._target}: {error}"
            ) from error
        except CybroError as error:
            raise UpdateFailed(
                f"Invalid response from {self._target}: {error}"
            ) from error

        return device

    def add_vars(self, variables: dict[str, VarType]) -> None:
        """Poll the variables of an entity."""
        for name, var_type in variables.items():
            self._var_users[name] = self._var_users.get(name, 0) + 1
            self.data.add_var(name, var_type=var_type)

    def remove_vars(self, names: Iterable[str]) -> None:
        """Stop polling the variables of an entity, unless another one uses them."""
        for name in names:
            users = self._var_users.pop(name, 0) - 1
            if users > 0:
                self._var_users[name] = users
            else:
                self.data.remove_var(name)

    @property
    def via_device_info(self) -> dict[str, str | None]:
        """Return the DeviceInfo fields linking a device to the controller."""
        return {"via_device_id": self.device_id}

    def get_value(
        self,
        tag: str,
        factor: float = 1.0,
        precision: int | None = 0,
        def_val: str | int | float | None = None,
    ) -> str | int | float | None:
        """Return a single Tag Value and format it with a specific factor."""
        res = self.data.vars.get(tag)
        if res is None:
            return def_val
        if res.value == "?" or res.value is None:
            LOGGER.debug("get_value: %s -> ? (%s)", tag, def_val)
            return def_val
        if precision is None:
            LOGGER.debug("get_value: %s -> %s", tag, res.value)
            return res.value
        try:
            # try to parse float value, if fails, try to return int, else return as string
            if factor != 1.0 or precision != 0 or any(c in res.value for c in ",."):
                converted_numerical_value = float(res.value.replace(",", "")) * factor
                value = f"{converted_numerical_value:z.{precision}f}"
                LOGGER.debug("get_value: %s -> %s", tag, value)
                return float(value)
            LOGGER.debug("get_value: %s -> %s", tag, res.value)
            return int(res.value)
        except ValueError:
            LOGGER.debug("get_value: %s -> %s", tag, res.value)
            return res.value

    def get_template_value(
        self,
        tag: str,
        value_template: Template | None = None,
        def_val: bool | str | int | float | None = None,
    ) -> bool | str | int | float | None:
        """Return a single Tag Value and format it with a given template."""
        res = self.data.vars.get(tag)
        if res is None:
            return def_val
        if res.value == "?" or res.value is None:
            LOGGER.debug("get_template_value: %s -> ? (%s)", tag, def_val)
            return def_val
        value = res.value
        if value_template is not None:
            value = value_template.async_render_with_possible_json_value(value, None)
        LOGGER.debug("get_template_value: %s -> %s", tag, value)
        return value
