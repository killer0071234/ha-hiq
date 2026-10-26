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
from cybro.abus import SocketMessage
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.const import CONF_PASSWORD
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.template import Template
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import CONF_CONNECTION
from .const import CONNECTION_DIRECT
from .const import DEFAULT_HOST
from .const import DOMAIN
from .const import HIQ_SOCKET
from .const import INPUT_EVENT_TYPES
from .const import LOGGER
from .const import SCAN_INTERVAL
from .const import SCAN_INTERVAL_ADDON
from .const import SCAN_INTERVAL_DIRECT
from .const import SOCKET_INPUT_EVENT
from .const import SOCKET_REFRESH_DELAY


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
        # event entities of the button inputs, by input number
        self._input_listeners: dict[int, Callable[[str], None]] = {}
        self.has_socket = False

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

    @callback
    def async_setup_socket(self) -> None:
        """Receive socket 1 of a directly connected HIQ controller.

        Only if all its variables are in the program, so a socket 1 of
        another program is never read as an HIQ message.
        """
        if not isinstance(self.cybro, CybroDirect):
            return
        plc_vars = self.data.plc_info.plc_vars
        if any(
            f"{self.unique_id}.{name}" not in plc_vars
            for name, _ in HIQ_SOCKET.slots()
        ):
            return
        self._socket_refresh = Debouncer(
            self.hass,
            LOGGER,
            cooldown=SOCKET_REFRESH_DELAY,
            immediate=False,
            function=self.async_refresh,
        )
        self.cybro.add_socket(HIQ_SOCKET)
        self.cybro.on_socket(self._socket_received)
        self.has_socket = True

    @callback
    def async_add_input_listener(
        self, number: int, listener: Callable[[str], None]
    ) -> Callable[[], None]:
        """Call listener(event type) for the events of a button input."""
        self._input_listeners[number] = listener
        return lambda: self._input_listeners.pop(number, None)

    @callback
    def _socket_received(self, message: SocketMessage) -> None:
        """Handle a socket 1 message, refresh the values a second later."""
        values = message.values
        LOGGER.debug("c%s sent socket %s: %s", message.nad, message.socket_id, values)
        # socket_req only makes the program send the socket, it is not checked;
        # input events are those of the controller's own inputs
        if (
            values["socket_command"] == SOCKET_INPUT_EVENT
            and values["socket_from"] == message.nad
            and (listener := self._input_listeners.get(values["socket_argument_0"]))
            and 0 <= (event := values["socket_argument_1"]) < len(INPUT_EVENT_TYPES)
        ):
            listener(INPUT_EVENT_TYPES[event])
        self._socket_refresh.async_schedule_call()

    async def async_shutdown(self) -> None:
        """Stop the socket handling, eg: when the entry is unloaded."""
        await super().async_shutdown()
        if self.has_socket:
            self._socket_refresh.async_shutdown()
        # only removes the socket handler of a direct controller, a session of
        # Home Assistant is never closed
        await self.cybro.disconnect()

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
