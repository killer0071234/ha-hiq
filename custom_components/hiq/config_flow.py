"""Config flow to configure the HIQ-Home integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from cybro import Cybro
from cybro import CybroConnectionError
from cybro import Device
from homeassistant.const import CONF_ADDRESS
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_PORT
from homeassistant.core import async_get_hass
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DEFAULT_HOST
from .const import DEFAULT_PORT
from .const import DOMAIN
from .const import LOGGER

from . import COMBINED_SCHEMA

PLC_SETUP = {
    vol.Required(CONF_HOST, default=DEFAULT_HOST): TextSelector(
        TextSelectorConfig(type=TextSelectorType.TEXT)
    ),
    vol.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
        NumberSelectorConfig(min=1, max=65535, step=1, mode=NumberSelectorMode.BOX)
    ),
    vol.Required(CONF_ADDRESS, default=1000): NumberSelector(
        NumberSelectorConfig(min=1, step=1, mode=NumberSelectorMode.BOX)
    ),
}
DATA_SCHEMA_PLC = vol.Schema(PLC_SETUP)


async def validate_plc_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate new plc setup."""
    hass = async_get_hass()

    plc_config: dict[str, Any] = COMBINED_SCHEMA(user_input)

    # abort if the config already exists
    handler.parent_handler._async_abort_entries_match(
        {
            CONF_HOST: plc_config[CONF_HOST],
            CONF_PORT: plc_config[CONF_PORT],
            CONF_ADDRESS: plc_config[CONF_ADDRESS],
        }
    )

    # convert values to int
    plc_config[CONF_PORT] = int(plc_config[CONF_PORT])
    plc_config[CONF_ADDRESS] = int(plc_config[CONF_ADDRESS])
    try:
        device = await _async_get_device(
            hass,
            plc_config[CONF_HOST],
            plc_config[CONF_PORT],
            plc_config[CONF_ADDRESS],
        )

        if device.server_info.scgi_port_status == "":
            raise SchemaFlowError("scgi_server_not_running")
        if device.plc_info.plc_program_status != "ok":
            raise SchemaFlowError("plc_not_existing")

        return plc_config

    except CybroConnectionError:
        LOGGER.error(
            "Can not connect to cybro scgi server: %s:%s",
            plc_config[CONF_HOST],
            plc_config[CONF_PORT],
        )
        raise SchemaFlowError("cannot_connect")


async def _async_get_device(hass, host: str, port: int, address: int) -> Device:
    """Get device information from Cybro device."""
    session = async_get_clientsession(hass)
    cybro = Cybro(host, port=port, session=session, nad=address)
    return await cybro.update(
        plc_nad=address,
        device_type=1,
    )


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=DATA_SCHEMA_PLC,
        validate_user_input=validate_plc_setup,
    )
}


class HiqFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a HIQ-Home config flow."""

    VERSION = 2

    config_flow = CONFIG_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return f"c{options[CONF_ADDRESS]}@{options[CONF_HOST]}:{options[CONF_PORT]}"
