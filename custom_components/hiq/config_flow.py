"""Config flow to configure the HIQ-Home integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from cybro import Cybro
from cybro import CybroConnectionError
from cybro import Device
from homeassistant.config_entries import ConfigEntry
from homeassistant.config_entries import ConfigFlow
from homeassistant.config_entries import OptionsFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_IGNORE_GENERAL_ERROR
from .const import DOMAIN
from .const import LOGGER


class HiqFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a HIQ-Home config flow."""

    VERSION = 1
    discovered_host: str
    discovered_device: Device

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HiqOptionsFlowHandler:
        """Get the options flow for this handler."""
        return HiqOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            try:
                device = await self._async_get_device(
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_ADDRESS],
                )
            except CybroConnectionError:
                errors["base"] = "cannot_connect"
                LOGGER.error(
                    "Can not connect to cybro scgi server: %s:%s",
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                )
            else:
                if device.server_info.scgi_port_status == "":
                    return self.async_abort(reason="scgi_server_not_running")
                if device.plc_info.plc_program_status != "ok":
                    return self.async_abort(
                        reason="plc_not_existing",
                        description_placeholders={"address": user_input[CONF_ADDRESS]},
                    )
                title_name = f"c{user_input[CONF_ADDRESS]}@{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                await self.async_set_unique_id(title_name)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=title_name,
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_ADDRESS: user_input[CONF_ADDRESS],
                        CONF_IGNORE_GENERAL_ERROR: user_input[
                            CONF_IGNORE_GENERAL_ERROR
                        ],
                    },
                )
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default="localhost"): str,
                    vol.Required(CONF_PORT, default=4000): int,
                    vol.Required(CONF_ADDRESS, default=1000): int,
                    vol.Required(CONF_IGNORE_GENERAL_ERROR, default=False): bool,
                }
            ),
            errors=errors or {},
        )

    async def _async_get_device(self, host: str, port: int, address: int) -> Device:
        """Get device information from Cybro device."""
        session = async_get_clientsession(self.hass)
        cybro = Cybro(host, port=port, session=session, nad=address)
        return await cybro.update(plc_nad=address)


class HiqOptionsFlowHandler(OptionsFlow):
    """Handle HIQ-Home options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize HIQ-Home options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage HIQ-Home options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_IGNORE_GENERAL_ERROR,
                        default=self.config_entry.options.get(
                            CONF_IGNORE_GENERAL_ERROR, False
                        ),
                    ): bool,
                }
            ),
        )
