"""Config flow to configure the HIQ-Home integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from cybro import Cybro
from cybro import CybroConnectionError
from cybro import Device
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_HOST
from .const import DEFAULT_PORT
from .const import DOMAIN
from .const import LOGGER


class HiqFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a HIQ-Home config flow."""

    VERSION = 1
    discovered_host: str
    discovered_device: Device

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
                    },
                )
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_ADDRESS, default=1000): int,
                }
            ),
            errors=errors or {},
        )

    async def _async_get_device(self, host: str, port: int, address: int) -> Device:
        """Get device information from Cybro device."""
        session = async_get_clientsession(self.hass)
        cybro = Cybro(host, port=port, session=session, nad=address)
        return await cybro.update(
            plc_nad=address,
            device_type=1,
        )
