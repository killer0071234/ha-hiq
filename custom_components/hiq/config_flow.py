"""Config flow to configure the HIQ-Home integration."""

from __future__ import annotations

import ipaddress
import uuid
from collections.abc import Callable
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from cybro import Cybro
from cybro import CybroConnectionError
from cybro import CybroDirect
from cybro import Device
from cybro.abus import AbusResponseError
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import CONF_STATE_CLASS
from homeassistant.components.sensor import DEVICE_CLASS_UNITS
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorStateClass
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.config_entries import ConfigEntry
from homeassistant.config_entries import ConfigFlow
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_OPTIONS
from homeassistant.const import CONF_PASSWORD
from homeassistant.const import CONF_PORT
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant
from homeassistant.core import async_get_hass
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.schema_config_entry_flow import SchemaCommonFlowHandler
from homeassistant.helpers.schema_config_entry_flow import SchemaFlowError
from homeassistant.helpers.schema_config_entry_flow import SchemaFlowFormStep
from homeassistant.helpers.schema_config_entry_flow import SchemaFlowMenuStep
from homeassistant.helpers.schema_config_entry_flow import SchemaOptionsFlowHandler
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
from .const import CONF_CONNECTION
from .const import CONF_INDEX
from .const import CONF_TAG
from .const import CONNECTION_DIRECT
from .const import CONNECTION_SCGI
from .const import DEFAULT_HOST
from .const import DEFAULT_PORT
from .const import DOCS_URL
from .const import DOMAIN
from .const import LOGGER
from .discovery import CONF_VERSION
from .transport import async_get_transport
from .transport import async_release_transport

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

DIRECT_SETUP = {
    vol.Required(CONF_ADDRESS): NumberSelector(
        NumberSelectorConfig(min=1, step=1, mode=NumberSelectorMode.BOX)
    ),
    vol.Optional(CONF_IP_ADDRESS): TextSelector(),
    # the A-bus password is sent as 16 bit transaction id
    vol.Optional(CONF_PASSWORD): NumberSelector(
        NumberSelectorConfig(min=0, max=65535, step=1, mode=NumberSelectorMode.BOX)
    ),
}

# options that describe how the controller is reached (the rest are entities)
CONNECTION_KEYS = (
    CONF_CONNECTION,
    CONF_ADDRESS,
    CONF_HOST,
    CONF_PORT,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
)


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

DATA_SCHEMA_DIRECT = vol.Schema(DIRECT_SETUP)

# a found controller: NAD and IP come from the scan
DATA_SCHEMA_DISCOVERED = vol.Schema(
    {key: value for key, value in DIRECT_SETUP.items() if key == CONF_PASSWORD}
)

DATA_SCHEMA_EDIT_SELECT = vol.Schema(SELECT_SETUP)

DATA_SCHEMA_EDIT_SENSOR = vol.Schema(SENSOR_SETUP)


class ControllerError(Exception):
    """The controller can't be reached, the error is shown in the form."""

    def __init__(self, error: str) -> None:
        """Initialize with the error key."""
        super().__init__(error)
        self.error = error


def _scgi_options(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return the options of a controller reached through the scgi server."""
    config: dict[str, Any] = COMBINED_SCHEMA(user_input)
    return {
        CONF_HOST: config[CONF_HOST],
        CONF_PORT: int(config[CONF_PORT]),
        CONF_ADDRESS: int(config[CONF_ADDRESS]),
        CONF_CONNECTION: CONNECTION_SCGI,
    }


def _direct_options(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return the options of a directly connected controller."""
    options: dict[str, Any] = {
        CONF_ADDRESS: int(user_input[CONF_ADDRESS]),
        CONF_CONNECTION: CONNECTION_DIRECT,
    }
    if ip := user_input.get(CONF_IP_ADDRESS, "").strip():
        try:
            ipaddress.IPv4Address(ip)
        except ValueError:
            raise ControllerError("invalid_ip") from None
        options[CONF_IP_ADDRESS] = ip
    if (password := user_input.get(CONF_PASSWORD)) is not None:
        options[CONF_PASSWORD] = int(password)
    return options


def _title(options: Mapping[str, Any]) -> str:
    """Return the config entry title."""
    if options[CONF_CONNECTION] == CONNECTION_DIRECT:
        return f"c{options[CONF_ADDRESS]}"
    return f"c{options[CONF_ADDRESS]}@{options[CONF_HOST]}:{options[CONF_PORT]}"


async def _async_check_scgi(hass: HomeAssistant, options: dict[str, Any]) -> None:
    """Check the scgi server reaches a running controller."""
    try:
        device = await _async_get_device(
            hass, options[CONF_HOST], options[CONF_PORT], options[CONF_ADDRESS]
        )
    except CybroConnectionError:
        LOGGER.error(
            "Can not connect to cybro scgi server: %s:%s",
            options[CONF_HOST],
            options[CONF_PORT],
        )
        raise ControllerError("cannot_connect") from None

    # scgi server 3.x reports a running controller as "ok", 2.x as "run"
    if device.plc_info.plc_status not in ("ok", "run"):
        raise ControllerError("plc_not_existing")


async def _async_check_direct(
    hass: HomeAssistant, options: dict[str, Any], flow_id: str
) -> None:
    """Check the controller answers and runs a program."""
    nad = options[CONF_ADDRESS]
    transport = await async_get_transport(hass, flow_id)
    try:
        cybro = CybroDirect(
            transport,
            nad,
            ip=options.get(CONF_IP_ADDRESS),
            password=options.get(CONF_PASSWORD),
        )
        response = await cybro.request({f"c{nad}.sys.plc_status": ""})
    except AbusResponseError as err:
        LOGGER.error("Controller c%s refused the connection: %s", nad, err)
        raise ControllerError("access_denied") from None
    except CybroConnectionError as err:
        LOGGER.error("Controller c%s doesn't answer: %s", nad, err)
        raise ControllerError("no_answer") from None
    finally:
        async_release_transport(hass, flow_id)
    if response["var"]["value"] != "ok":
        raise ControllerError("no_program")


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
    sensor: dict[str, Any] = handler.options[SENSOR_DOMAIN][handler.flow_state["_idx"]]
    # Default name is tag name, the tag is not part of the edit form
    if user_input.get(CONF_NAME) is None:
        user_input[CONF_NAME] = sensor[CONF_TAG]

    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly,
    # including popping omitted optional schema items.
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


class HiqFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a HIQ-Home config flow."""

    VERSION = 3

    _discovered: dict[str, Any]
    # scgi entry of a found controller, switched to the direct connection
    _switch_entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SchemaOptionsFlowHandler:
        """Return the options flow (custom entities)."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose how the controller is reached."""
        return self.async_show_menu(step_id="user", menu_options=["direct", "scgi"])

    async def async_step_direct(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a controller reached directly over A-bus (UDP)."""
        return await self._async_step_connection(
            "direct", DATA_SCHEMA_DIRECT, _direct_options, user_input
        )

    async def async_step_scgi(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a controller reached through the scgi server."""
        return await self._async_step_connection(
            "scgi", DATA_SCHEMA_PLC, _scgi_options, user_input
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the new connection of the controller."""
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=["reconfigure_direct", "reconfigure_scgi"],
        )

    async def async_step_reconfigure_direct(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Connect the controller directly."""
        return await self._async_step_connection(
            "reconfigure_direct", DATA_SCHEMA_DIRECT, _direct_options, user_input
        )

    async def async_step_reconfigure_scgi(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Connect the controller through the scgi server."""
        return await self._async_step_connection(
            "reconfigure_scgi", DATA_SCHEMA_PLC, _scgi_options, user_input
        )

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Offer a controller found by the A-bus scan."""
        nad = discovery_info[CONF_ADDRESS]
        self._discovered = discovery_info
        self.context["title_placeholders"] = {"name": f"c{nad}"}
        entry = next(
            (
                entry
                for entry in self._async_current_entries(include_ignore=False)
                if entry.options.get(CONF_ADDRESS) == nad
            ),
            None,
        )
        if entry is not None:
            # own unique id: ignoring the offer must not touch the entry's id
            await self.async_set_unique_id(f"c{nad}_switch")
            self._abort_if_unique_id_configured()
            self._switch_entry = entry
            return await self.async_step_discovery_switch()
        await self.async_set_unique_id(f"c{nad}")
        self._abort_if_unique_id_configured()
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add the found controller."""
        return await self._async_step_connection(
            "discovery_confirm",
            DATA_SCHEMA_DISCOVERED,
            self._discovered_options,
            user_input,
        )

    async def async_step_discovery_switch(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Connect the found controller of an scgi entry directly."""
        return await self._async_step_connection(
            "discovery_switch",
            DATA_SCHEMA_DISCOVERED,
            self._discovered_options,
            user_input,
        )

    def _discovered_options(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Return the options of the found controller (found by broadcast)."""
        return _direct_options(
            {**user_input, CONF_ADDRESS: self._discovered[CONF_ADDRESS]}
        )

    def _description_placeholders(self, step_id: str) -> dict[str, str] | None:
        """Return the placeholders of a form."""
        if step_id.endswith("scgi"):
            return {"docs_url": DOCS_URL}
        if self.source != SOURCE_INTEGRATION_DISCOVERY:
            return None
        placeholders = {
            "nad": str(self._discovered[CONF_ADDRESS]),
            "ip": self._discovered[CONF_IP_ADDRESS],
        }
        if self._switch_entry is not None:
            return placeholders | {"title": self._switch_entry.title}
        return placeholders | {"version": self._discovered[CONF_VERSION]}

    def _connection_entry(self) -> ConfigEntry | None:
        """Return the entry whose connection is changed, None for a new one."""
        if self.source == SOURCE_RECONFIGURE:
            return self._get_reconfigure_entry()
        return self._switch_entry

    async def _async_step_connection(
        self,
        step_id: str,
        schema: vol.Schema,
        get_options: Callable[[dict[str, Any]], dict[str, Any]],
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Show a connection form, check it and create or update the entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                options = get_options(user_input)
                await self._async_check_controller(options)
            except ControllerError as err:
                field = CONF_IP_ADDRESS if err.error == "invalid_ip" else "base"
                errors[field] = err.error
            else:
                return self._async_finish(options)
        suggested = user_input
        if suggested is None and self.source == SOURCE_RECONFIGURE:
            suggested = self._get_reconfigure_entry().options
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
            description_placeholders=self._description_placeholders(step_id),
        )

    async def _async_check_controller(self, options: dict[str, Any]) -> None:
        """Abort for a controller that is already set up, check it answers."""
        nad = options[CONF_ADDRESS]
        if (entry := self._connection_entry()) is not None:
            if nad != entry.options[CONF_ADDRESS]:
                raise AbortFlow("wrong_controller")
        else:
            # entries of the same controller from before version 3 keep an
            # old unique id, so also compare the NAD
            await self.async_set_unique_id(f"c{nad}")
            self._abort_if_unique_id_configured()
            self._async_abort_entries_match({CONF_ADDRESS: nad})
        if options[CONF_CONNECTION] == CONNECTION_DIRECT:
            await _async_check_direct(self.hass, options, self.flow_id)
        else:
            await _async_check_scgi(self.hass, options)

    @callback
    def _async_finish(self, options: dict[str, Any]) -> ConfigFlowResult:
        """Create the entry, or update the connection of an existing one."""
        if (entry := self._connection_entry()) is None:
            return self.async_create_entry(
                title=_title(options), data={}, options=options
            )
        entities = {
            key: value
            for key, value in entry.options.items()
            if key not in CONNECTION_KEYS
        }
        return self.async_update_reload_and_abort(
            entry,
            title=_title(options),
            options=options | entities,
            reason=(
                "reconfigure_successful"
                if self.source == SOURCE_RECONFIGURE
                else "switched"
            ),
        )
