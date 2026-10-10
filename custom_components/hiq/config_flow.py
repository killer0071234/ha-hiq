"""Config flow to configure the HIQ-Home integration."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from cybro import Cybro
from cybro import CybroConnectionError
from cybro import Device
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import CONF_STATE_CLASS
from homeassistant.components.sensor import DEVICE_CLASS_UNITS
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import CONF_ADDRESS
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_OPTIONS
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


def _tag_selector(handler: SchemaCommonFlowHandler) -> SelectSelector:
    """Return a selector of the controller variables, without the prefix."""
    hass = async_get_hass()

    coordinator = hass.data.get(DOMAIN)[handler.parent_handler.config_entry.entry_id]
    var_prefix = f"c{handler.options.get(CONF_ADDRESS)}."

    # remove foreign variables and the prefix
    variables = [
        var.removeprefix(var_prefix)
        for var in coordinator.data.plc_info.plc_vars
        if var_prefix in var
    ]

    return SelectSelector(
        SelectSelectorConfig(
            options=variables,
            mode=SelectSelectorMode.DROPDOWN,
            sort=True,
        )
    )


async def get_sensor_setup(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return sensor setup schema."""
    return vol.Schema(
        {
            vol.Required(CONF_TAG): _tag_selector(handler),
            **SENSOR_SETUP,
        }
    )


async def get_select_setup(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return select setup schema."""
    return vol.Schema(
        {
            vol.Required(CONF_TAG): _tag_selector(handler),
            **SELECT_SETUP,
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

SELECT_SETUP = {
    vol.Optional(CONF_NAME): TextSelector(),
    # options are entered as label=value, eg: eco=1
    vol.Required(CONF_OPTIONS): SelectSelector(
        SelectSelectorConfig(
            options=[],
            multiple=True,
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    ),
}

DATA_SCHEMA_PLC = vol.Schema(PLC_SETUP)

DATA_SCHEMA_EDIT_SELECT = vol.Schema(SELECT_SETUP)

DATA_SCHEMA_EDIT_SENSOR = vol.Schema(SENSOR_SETUP)


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
    except CybroConnectionError:
        LOGGER.error(
            "Can not connect to cybro scgi server: %s:%s",
            plc_config[CONF_HOST],
            plc_config[CONF_PORT],
        )
        raise SchemaFlowError("cannot_connect")

    # scgi server 3.x reports a running controller as "ok", 2.x as "run"
    if device.plc_info.plc_status not in ("ok", "run"):
        raise SchemaFlowError("plc_not_existing")

    return plc_config


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
    user_input[CONF_UNIQUE_ID] = str(uuid.uuid1())

    # Default name is tag name
    if user_input.get(CONF_NAME) is None:
        user_input[CONF_NAME] = user_input[CONF_TAG]

    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    sensors: list[dict[str, Any]] = handler.options.setdefault(SENSOR_DOMAIN, [])
    sensors.append(user_input)
    return {}


# options key holding the platform of the entity being edited, until it is saved
EDIT_PLATFORM = "_edit_platform"

# platforms of the custom entities, in the order they are listed
CUSTOM_PLATFORMS = (SENSOR_DOMAIN, SELECT_DOMAIN)


def _entity_key(platform: str, index: int) -> str:
    """Return the key of a custom entity, eg: sensor:0."""
    return f"{platform}:{index}"


def _parse_entity_key(key: str) -> tuple[str, int]:
    """Return platform and index of a custom entity key."""
    platform, index = key.split(":")
    return platform, int(index)


def _entity_names(handler: SchemaCommonFlowHandler) -> dict[str, str]:
    """Return the configured custom entity names by key."""
    return {
        _entity_key(platform, index): f"{config[CONF_NAME]} ({platform.capitalize()})"
        for platform in CUSTOM_PLATFORMS
        for index, config in enumerate(handler.options.get(platform, []))
    }


async def get_select_entity_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return schema for selecting a custom entity."""
    return vol.Schema({vol.Required(CONF_INDEX): vol.In(_entity_names(handler))})


def _parse_select_options(options: list[str]) -> dict[str, int]:
    """Return the select options entered as label=value by label."""
    if not options:
        raise SchemaFlowError("select_options_empty")
    result: dict[str, int] = {}
    for option in options:
        label, _, value = option.rpartition("=")
        label = label.strip()
        if not label:
            raise SchemaFlowError("select_option_invalid")
        try:
            number = int(value)
        except ValueError:
            raise SchemaFlowError("select_option_invalid") from None
        if label in result:
            raise SchemaFlowError("select_option_duplicate_label")
        if number in result.values():
            raise SchemaFlowError("select_option_duplicate_value")
        result[label] = number
    return result


async def validate_select_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate select input."""
    user_input[CONF_OPTIONS] = _parse_select_options(user_input[CONF_OPTIONS])
    user_input[CONF_UNIQUE_ID] = str(uuid.uuid1())

    # Default name is tag name
    if user_input.get(CONF_NAME) is None:
        user_input[CONF_NAME] = user_input[CONF_TAG]

    selects: list[dict[str, Any]] = handler.options.setdefault(SELECT_DOMAIN, [])
    selects.append(user_input)
    return {}


async def validate_select_entity(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Store the entity to edit in the flow state."""
    platform, index = _parse_entity_key(user_input[CONF_INDEX])
    handler.flow_state["_idx"] = index
    # the next step is chosen from the options only
    handler.options[EDIT_PLATFORM] = platform
    return {}


async def next_edit_step(options: dict[str, Any]) -> str:
    """Return the edit step of the selected entity."""
    return f"edit_{options[EDIT_PLATFORM]}"


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
    handler.options.pop(EDIT_PLATFORM, None)
    # Default name is tag name
    if user_input.get(CONF_NAME) is None:
        user_input[CONF_NAME] = user_input[CONF_TAG]

    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly,
    # including popping omitted optional schema items.
    sensor: dict[str, Any] = handler.options[SENSOR_DOMAIN][handler.flow_state["_idx"]]
    sensor.update(user_input)
    for key in DATA_SCHEMA_EDIT_SENSOR.schema:
        if isinstance(key, vol.Optional) and key not in user_input:
            # Key not present, delete keys old value (if present) too
            sensor.pop(key, None)
    return {}


async def get_edit_select_suggested_values(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Return suggested values for select editing."""
    select: dict[str, Any] = handler.options[SELECT_DOMAIN][handler.flow_state["_idx"]]
    return {
        CONF_NAME: select[CONF_NAME],
        CONF_OPTIONS: [
            f"{label}={value}" for label, value in select[CONF_OPTIONS].items()
        ],
    }


async def validate_select_edit(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Update edited select."""
    options = _parse_select_options(user_input[CONF_OPTIONS])
    handler.options.pop(EDIT_PLATFORM, None)

    select: dict[str, Any] = handler.options[SELECT_DOMAIN][handler.flow_state["_idx"]]
    select[CONF_OPTIONS] = options
    # Default name is tag name
    select[CONF_NAME] = user_input.get(CONF_NAME) or select[CONF_TAG]
    return {}


async def get_remove_entity_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return schema for custom entity removal."""
    return vol.Schema(
        {vol.Required(CONF_INDEX): cv.multi_select(_entity_names(handler))}
    )


async def validate_remove_entity(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate remove custom entities."""
    removed_keys: set[str] = set(user_input[CONF_INDEX])

    # Standard behavior is to merge the result with the options.
    # In this case, we want to remove sub-items so we update the options directly.
    entity_registry = er.async_get(handler.parent_handler.hass)
    for platform in CUSTOM_PLATFORMS:
        if platform not in handler.options:
            continue
        kept: list[dict[str, Any]] = []
        config: dict[str, Any]
        for index, config in enumerate(handler.options[platform]):
            if _entity_key(platform, index) not in removed_keys:
                kept.append(config)
            elif entity_id := entity_registry.async_get_entity_id(
                platform, DOMAIN, config[CONF_UNIQUE_ID]
            ):
                entity_registry.async_remove(entity_id)
        handler.options[platform] = kept
    return {}


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=DATA_SCHEMA_PLC,
        validate_user_input=validate_plc_setup,
    )
}

OPTIONS_FLOW = {
    "init": SchemaFlowMenuStep(["add_entity", "select_edit_entity", "remove_entity"]),
    "add_entity": SchemaFlowMenuStep(
        [f"add_{platform}" for platform in CUSTOM_PLATFORMS]
    ),
    "add_sensor": SchemaFlowFormStep(
        get_sensor_setup,
        suggested_values=None,
        validate_user_input=validate_sensor_setup,
    ),
    "add_select": SchemaFlowFormStep(
        get_select_setup,
        suggested_values=None,
        validate_user_input=validate_select_setup,
    ),
    "select_edit_entity": SchemaFlowFormStep(
        get_select_entity_schema,
        suggested_values=None,
        validate_user_input=validate_select_entity,
        next_step=next_edit_step,
    ),
    "edit_sensor": SchemaFlowFormStep(
        DATA_SCHEMA_EDIT_SENSOR,
        suggested_values=get_edit_sensor_suggested_values,
        validate_user_input=validate_sensor_edit,
    ),
    "edit_select": SchemaFlowFormStep(
        DATA_SCHEMA_EDIT_SELECT,
        suggested_values=get_edit_select_suggested_values,
        validate_user_input=validate_select_edit,
    ),
    "remove_entity": SchemaFlowFormStep(
        get_remove_entity_schema,
        suggested_values=None,
        validate_user_input=validate_remove_entity,
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
