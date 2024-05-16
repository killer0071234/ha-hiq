"""Config flow to configure the HIQ-Home integration."""
from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from cybro import Cybro
from cybro import CybroConnectionError
from cybro import Device
from homeassistant.components.sensor import CONF_STATE_CLASS
from homeassistant.components.sensor import DEVICE_CLASS_UNITS
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import CONF_ADDRESS
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_PORT
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.core import async_get_hass
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.schema_config_entry_flow import SchemaCommonFlowHandler
from homeassistant.helpers.schema_config_entry_flow import SchemaConfigFlowHandler
from homeassistant.helpers.schema_config_entry_flow import SchemaFlowError
from homeassistant.helpers.schema_config_entry_flow import SchemaFlowFormStep
from homeassistant.helpers.schema_config_entry_flow import SchemaFlowMenuStep
from homeassistant.helpers.selector import NumberSelector
from homeassistant.helpers.selector import NumberSelectorConfig
from homeassistant.helpers.selector import NumberSelectorMode
from homeassistant.helpers.selector import SelectSelector
from homeassistant.helpers.selector import SelectSelectorConfig
from homeassistant.helpers.selector import SelectSelectorMode
from homeassistant.helpers.selector import TemplateSelector
from homeassistant.helpers.selector import TextSelector
from homeassistant.helpers.selector import TextSelectorConfig
from homeassistant.helpers.selector import TextSelectorType

from . import COMBINED_SCHEMA
from .const import CONF_INDEX
from .const import CONF_TAG
from .const import DEFAULT_HOST
from .const import DEFAULT_PORT
from .const import DOMAIN
from .const import LOGGER

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


async def get_sensor_setup(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return sensor setup schema."""
    hass = async_get_hass()

    coordinator = hass.data.get(DOMAIN)[handler.parent_handler.config_entry.entry_id]
    var_prefix = f"c{handler.options.get(CONF_ADDRESS)}."

    variables = list(coordinator.data.vars.keys())
    # remove foreign variables and the prefix
    variables = [
        var.removeprefix(var_prefix) for var in variables if var.find(var_prefix) != -1
    ]

    return vol.Schema(
        {
            vol.Required(CONF_TAG): SelectSelector(
                SelectSelectorConfig(
                    options=variables,
                    mode=SelectSelectorMode.DROPDOWN,
                    sort=True,
                )
            ),
            **SENSOR_SETUP,
        }
    )


SENSOR_SETUP = {
    vol.Optional(CONF_NAME): TextSelector(),
    vol.Optional(CONF_VALUE_TEMPLATE): TemplateSelector(),
    vol.Optional(CONF_DEVICE_CLASS): SelectSelector(
        SelectSelectorConfig(
            options=[
                cls.value for cls in SensorDeviceClass if cls != SensorDeviceClass.ENUM
            ],
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="sensor_device_class",
            sort=True,
        )
    ),
    vol.Optional(CONF_STATE_CLASS): SelectSelector(
        SelectSelectorConfig(
            options=[cls.value for cls in SensorStateClass],
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="sensor_state_class",
            sort=True,
        )
    ),
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): SelectSelector(
        SelectSelectorConfig(
            options=list(
                {
                    str(unit)
                    for units in DEVICE_CLASS_UNITS.values()
                    for unit in units
                    if unit is not None
                }
            ),
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="sensor_unit_of_measurement",
            sort=True,
        )
    ),
}

DATA_SCHEMA_PLC = vol.Schema(PLC_SETUP)

DATA_SCHEMA_EDIT_SENSOR = vol.Schema(SENSOR_SETUP)
DATA_SCHEMA_SENSOR = vol.Schema(
    {
        # vol.Optional(CONF_NAME): TextSelector(),
        **SENSOR_SETUP,
    }
)


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


async def validate_sensor_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate sensor input."""
    # user_input[CONF_INDEX] = int(user_input[CONF_INDEX])
    user_input[CONF_UNIQUE_ID] = str(uuid.uuid1())

    # Default name is tag name
    if user_input.get(CONF_NAME) is None:
        user_input[CONF_NAME] = user_input[CONF_TAG]

    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    sensors: list[dict[str, Any]] = handler.options.setdefault(SENSOR_DOMAIN, [])
    sensors.append(user_input)
    return {}


async def validate_select_sensor(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Store sensor index in flow state."""
    handler.flow_state["_idx"] = int(user_input[CONF_INDEX])
    return {}


async def get_select_sensor_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return schema for selecting a sensor."""
    return vol.Schema(
        {
            vol.Required(CONF_INDEX): vol.In(
                {
                    str(index): config[CONF_NAME]
                    for index, config in enumerate(handler.options[SENSOR_DOMAIN])
                },
            )
        }
    )


async def get_edit_sensor_suggested_values(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Return suggested values for sensor editing."""
    idx: int = handler.flow_state["_idx"]
    return dict(handler.options[SENSOR_DOMAIN][idx])


async def validate_sensor_edit(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Update edited sensor."""
    # user_input[CONF_INDEX] = int(user_input[CONF_INDEX])

    # Default name is tag name
    if user_input.get(CONF_NAME) is None:
        user_input[CONF_NAME] = user_input[CONF_TAG]

    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly,
    # including popping omitted optional schema items.
    idx: int = handler.flow_state["_idx"]
    handler.options[SENSOR_DOMAIN][idx].update(user_input)
    for key in DATA_SCHEMA_EDIT_SENSOR.schema:
        if isinstance(key, vol.Optional) and key not in user_input:
            # Key not present, delete keys old value (if present) too
            handler.options[SENSOR_DOMAIN][idx].pop(key, None)
    return {}


async def get_remove_sensor_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return schema for sensor removal."""
    return vol.Schema(
        {
            vol.Required(CONF_INDEX): cv.multi_select(
                {
                    str(index): config[CONF_NAME]
                    for index, config in enumerate(handler.options[SENSOR_DOMAIN])
                },
            )
        }
    )


async def validate_remove_sensor(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate remove sensor."""
    removed_indexes: set[str] = set(user_input[CONF_INDEX])

    # Standard behavior is to merge the result with the options.
    # In this case, we want to remove sub-items so we update the options directly.
    entity_registry = er.async_get(handler.parent_handler.hass)
    sensors: list[dict[str, Any]] = []
    sensor: dict[str, Any]
    for index, sensor in enumerate(handler.options[SENSOR_DOMAIN]):
        if str(index) not in removed_indexes:
            sensors.append(sensor)
        elif entity_id := entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, sensor[CONF_UNIQUE_ID]
        ):
            entity_registry.async_remove(entity_id)
    handler.options[SENSOR_DOMAIN] = sensors
    return {}


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=DATA_SCHEMA_PLC,
        validate_user_input=validate_plc_setup,
    )
}

OPTIONS_FLOW = {
    "init": SchemaFlowMenuStep(["add_sensor", "select_edit_sensor", "remove_sensor"]),
    "add_sensor": SchemaFlowFormStep(
        get_sensor_setup,
        suggested_values=None,
        validate_user_input=validate_sensor_setup,
    ),
    "select_edit_sensor": SchemaFlowFormStep(
        get_select_sensor_schema,
        suggested_values=None,
        validate_user_input=validate_select_sensor,
        next_step="edit_sensor",
    ),
    "edit_sensor": SchemaFlowFormStep(
        DATA_SCHEMA_EDIT_SENSOR,
        suggested_values=get_edit_sensor_suggested_values,
        validate_user_input=validate_sensor_edit,
    ),
    "remove_sensor": SchemaFlowFormStep(
        get_remove_sensor_schema,
        suggested_values=None,
        validate_user_input=validate_remove_sensor,
    ),
}


class HiqFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a HIQ-Home config flow."""

    VERSION = 2

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return f"c{options[CONF_ADDRESS]}@{options[CONF_HOST]}:{options[CONF_PORT]}"
