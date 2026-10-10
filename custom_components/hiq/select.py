"""Support for HIQ-Home select."""

from __future__ import annotations

from dataclasses import dataclass
from re import search
from re import sub

from cybro import VarType
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.select import SelectEntity
from homeassistant.components.select import SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_OPTIONS
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import get_write_req_th
from .const import ATTR_DESCRIPTION
from .const import ATTR_VARIABLE
from .const import CONF_TAG
from .const import DOMAIN
from .const import LOGGER
from .coordinator import HiqDataUpdateCoordinator
from .light import is_general_error_ok
from .models import HiqEntity
from .models import custom_device_info
from .models import thermostat_device_info
from .models import hvac_device_info

HA_TO_CYBRO_TEMP_SOURCE_MAP = {
    "internal_sensor": 0,
    "external_sensor": 1,
    "remote_sensor": 2,
}

HA_TO_CYBRO_DISPLAY_MODE_MAP = {
    "nothing": 0,
    "minus": 1,
    "temperature": 2,
}

HA_TO_CYBRO_HVAC_MODE_MAP = {
    "none": 0,
    "heating": 1,
    "cooling": 2,
}

HA_TO_CYBRO_FAN_LIMIT_MAP = {
    "off": 0,
    "fan1": 1,
    "fan2": 2,
    "fan3": 3,
    "max": 4,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HIQ-Home select based on a config entry."""
    coordinator: HiqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    th_tags = add_th_tags(
        coordinator,
    )
    if th_tags is not None:
        async_add_entities(th_tags)

    hvac_tags = add_hvac_tags(
        coordinator,
    )
    if hvac_tags is not None:
        async_add_entities(hvac_tags)

    async_add_entities(add_custom_selects(coordinator, entry))


def add_custom_selects(
    coordinator: HiqDataUpdateCoordinator, entry: ConfigEntry
) -> list[HiqSelectEntity]:
    """Return the user defined selects of the config entry options."""
    var_prefix = f"c{coordinator.cybro.nad}."
    dev_info = custom_device_info(coordinator)
    return [
        HiqSelectEntity(
            coordinator=coordinator,
            # no translation key, the name is user defined
            entity_description=SelectEntityDescription(
                key=f"{var_prefix}{select[CONF_TAG]}",
                name=select[CONF_NAME],
                has_entity_name=True,
            ),
            attr_options=select[CONF_OPTIONS],
            unique_id=select[CONF_UNIQUE_ID],
            dev_info=dev_info,
        )
        for select in entry.options.get(SELECT_DOMAIN, [])
    ]


@dataclass
class HiqSelectEntityDescription[T](SelectEntityDescription):
    """HIQ Select Entity Description."""

    def __post_init__(self):
        """Defaults the translation_key to the sensor key."""
        self.has_entity_name = True
        self.translation_key = (
            self.translation_key
            or sub(r"c\d+\.", "", self.key).replace(".", "_").lower()
        )


# thermostat selects: name -> options
TH_SELECT_OPTIONS = {
    "temperature_source": HA_TO_CYBRO_TEMP_SOURCE_MAP,
    "display_mode": HA_TO_CYBRO_DISPLAY_MODE_MAP,
    "fan_limit": HA_TO_CYBRO_FAN_LIMIT_MAP,
}

# hvac selects: tag after cNAD -> (translation key, options)
HVAC_SELECTS = {
    ".hvac_mode": ("hvac_mode", HA_TO_CYBRO_HVAC_MODE_MAP),
    ".hvac_temperature_source": ("temperature_source", HA_TO_CYBRO_TEMP_SOURCE_MAP),
    ".hvac_display_mode": ("display_mode", HA_TO_CYBRO_DISPLAY_MODE_MAP),
}


def add_th_tags(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqSelectEntity] | None:
    """Find select for thermostat tags in the plc vars.
    eg: c1000.th00_window_enable and so on.
    """
    res: list[HiqSelectEntity] = []

    # find different thermostat vars
    for key in coordinator.data.plc_info.plc_vars:
        # identifier is cNAD.thNR
        grp = search(r"c\d+\.th\d+", key)
        unique_id = grp.group() if grp else key
        name = key.removeprefix(f"{unique_id}_")
        if name == key or name not in TH_SELECT_OPTIONS:
            continue
        # get if active
        if not is_general_error_ok(coordinator, key):
            continue
        res.append(
            HiqSelectEntity(
                coordinator=coordinator,
                entity_description=HiqSelectEntityDescription(
                    key=key,
                    translation_key=name,
                    entity_category=EntityCategory.CONFIG,
                    entity_registry_enabled_default=False,
                ),
                attr_options=TH_SELECT_OPTIONS[name],
                var_write_req=get_write_req_th(key, unique_id),
                dev_info=thermostat_device_info(coordinator, unique_id),
            )
        )

    if len(res) > 0:
        return res
    return None


def add_hvac_tags(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqSelectEntity] | None:
    """Find and add HVAC tags in the plc vars.
    eg: c1000.outdoor_temperature and so on.
    """
    res: list[HiqSelectEntity] = []

    # find different hvac related vars
    for key in coordinator.data.plc_info.plc_vars:
        # identifier is cNAD
        grp = search(r"c\d+", key)
        if not grp or not key.startswith(grp.group()):
            continue
        unique_id = grp.group()
        tag = key.removeprefix(unique_id)
        if tag not in HVAC_SELECTS:
            continue
        translation_key, options = HVAC_SELECTS[tag]
        res.append(
            HiqSelectEntity(
                coordinator=coordinator,
                entity_description=HiqSelectEntityDescription(
                    key=key,
                    translation_key=translation_key,
                    entity_category=EntityCategory.CONFIG,
                    entity_registry_enabled_default=False,
                ),
                attr_options=options,
                var_write_req=None,
                dev_info=hvac_device_info(coordinator, unique_id),
            )
        )

    if len(res) > 0:
        return res
    return None


class HiqSelectEntity(HiqEntity, SelectEntity):
    """Defines a HIQ-Home select entity."""

    def __init__(
        self,
        coordinator: HiqDataUpdateCoordinator,
        attr_options: dict[str, int],
        entity_description: SelectEntityDescription | None = None,
        unique_id: str | None = None,
        var_write_req: str | None = None,
        dev_info: DeviceInfo = None,
    ) -> None:
        """Initialize a HIQ-Home select entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = entity_description
        self._var = entity_description.key
        self._attr_unique_id = unique_id or self._var
        self._var_write_req = var_write_req
        self._attr_device_info = dev_info

        LOGGER.debug(self._attr_unique_id)
        coordinator.data.add_var(self._var, var_type=VarType.INT)
        self._attr_options = list(attr_options)
        self._var_map = attr_options
        self._option_by_value = {value: key for key, value in attr_options.items()}

    @property
    def current_option(self) -> str | None:
        """Return the option."""
        return self._option_by_value.get(self.coordinator.get_value(self._var))

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        try:
            desc = self.coordinator.data.vars[self._var].description
        except KeyError:
            desc = "?"
        return {
            ATTR_DESCRIPTION: desc,
            ATTR_VARIABLE: self._var,
        }

    async def async_select_option(self, option: str) -> None:
        """Set new option."""
        value = self._var_map[option]
        if self._var_write_req:
            LOGGER.debug(
                "write value: %s -> %s (%s) (+%s)",
                self._var,
                value,
                option,
                self._var_write_req,
            )
            await self.coordinator.cybro.request(
                {self._var: value, self._var_write_req: "1"}
            )
        else:
            LOGGER.debug("write value: %s -> %s (%s)", self._var, value, option)
            await self.coordinator.cybro.write_var(self._var, value)
        await self.coordinator.async_refresh()
