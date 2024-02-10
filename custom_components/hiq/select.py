"""Support for HIQ-Home select."""
from __future__ import annotations

from re import search, sub
from dataclasses import dataclass
from typing import Generic, TypeVar

from cybro import VarType
from homeassistant.components.select import (
    SelectEntity,
    SelectEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    AREA_CLIMATE,
    ATTR_DESCRIPTION,
    DOMAIN,
    LOGGER,
    MANUFACTURER,
)
from .coordinator import HiqDataUpdateCoordinator
from .light import is_general_error_ok
from .models import HiqEntity
from . import get_write_req_th

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


T = TypeVar("T")


@dataclass
class HiqSelectEntityDescription(Generic[T], SelectEntityDescription):
    """HIQ Select Entity Description."""

    def __post_init__(self):
        """Defaults the translation_key to the sensor key."""
        self.has_entity_name = True
        self.translation_key = (
            self.translation_key
            or sub(r"c\d+\.", "", self.key).replace(".", "_").lower()
        )


def add_th_tags(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqSelectEntity] | None:
    """Find select for thermostat tags in the plc vars.
    eg: c1000.th00_window_enable and so on.
    """
    res: list[HiqSelectEntity] = []

    # find different thermostat vars
    for key in coordinator.data.plc_info.plc_vars:
        unique_id = key
        # identifier is cNAD.thNR
        grp = search(r"c\d+\.th\d+", key)
        if grp:
            unique_id = grp.group()
        dev_info = DeviceInfo(
            identifiers={(coordinator.cybro.nad, f"{unique_id} thermostat")},
            manufacturer=MANUFACTURER,
            name=f"{unique_id} thermostat",
            suggested_area=AREA_CLIMATE,
            via_device=(DOMAIN, coordinator.cybro.nad),
        )
        # get if active
        ge_ok = is_general_error_ok(coordinator, key)

        # temperature source
        if key in (f"{unique_id}_temperature_source",):
            if ge_ok:
                res.append(
                    HiqSelectEntity(
                        coordinator=coordinator,
                        entity_description=HiqSelectEntityDescription(
                            key=key,
                            translation_key="temperature_source",
                            entity_category=EntityCategory.CONFIG,
                            entity_registry_enabled_default=False,
                        ),
                        attr_options=HA_TO_CYBRO_TEMP_SOURCE_MAP,
                        var_write_req=get_write_req_th(key, unique_id),
                        dev_info=dev_info,
                    )
                )
        # display mode
        elif key in (f"{unique_id}_display_mode",):
            if ge_ok:
                res.append(
                    HiqSelectEntity(
                        coordinator=coordinator,
                        entity_description=HiqSelectEntityDescription(
                            key=key,
                            translation_key="display_mode",
                            entity_category=EntityCategory.CONFIG,
                            entity_registry_enabled_default=False,
                        ),
                        attr_options=HA_TO_CYBRO_DISPLAY_MODE_MAP,
                        var_write_req=get_write_req_th(key, unique_id),
                        dev_info=dev_info,
                    )
                )
        # fan limit
        elif key in (f"{unique_id}_fan_limit",):
            if ge_ok:
                res.append(
                    HiqSelectEntity(
                        coordinator=coordinator,
                        entity_description=HiqSelectEntityDescription(
                            key=key,
                            translation_key="fan_limit",
                            entity_category=EntityCategory.CONFIG,
                            entity_registry_enabled_default=False,
                        ),
                        attr_options=HA_TO_CYBRO_FAN_LIMIT_MAP,
                        var_write_req=get_write_req_th(key, unique_id),
                        dev_info=dev_info,
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
        unique_id = key
        # identifier is cNAD
        grp = search(r"c\d+", key)
        if grp:
            unique_id = grp.group()
        dev_info = DeviceInfo(
            identifiers={(coordinator.cybro.nad, f"{unique_id} HVAC")},
            manufacturer=MANUFACTURER,
            name=f"{unique_id} HVAC",
            suggested_area=AREA_CLIMATE,
            via_device=(DOMAIN, coordinator.cybro.nad),
        )

        # get hvac mode
        if key in (f"{unique_id}.hvac_mode",):
            res.append(
                HiqSelectEntity(
                    coordinator=coordinator,
                    entity_description=HiqSelectEntityDescription(
                        key=key,
                        translation_key="hvac_mode",
                        entity_category=EntityCategory.CONFIG,
                        entity_registry_enabled_default=False,
                    ),
                    var_write_req=None,
                    attr_options=HA_TO_CYBRO_HVAC_MODE_MAP,
                    dev_info=dev_info,
                )
            )
        # temperature source
        if key in (f"{unique_id}_temperature_source",):
            res.append(
                HiqSelectEntity(
                    coordinator=coordinator,
                    entity_description=HiqSelectEntityDescription(
                        key=key,
                        translation_key="temperature_source",
                        entity_category=EntityCategory.CONFIG,
                        entity_registry_enabled_default=False,
                    ),
                    attr_options=HA_TO_CYBRO_TEMP_SOURCE_MAP,
                    var_write_req=None,
                    dev_info=dev_info,
                )
            )
        # display mode
        elif key in (f"{unique_id}.hvac_display_mode",):
            res.append(
                HiqSelectEntity(
                    coordinator=coordinator,
                    entity_description=HiqSelectEntityDescription(
                        key=key,
                        translation_key="display_mode",
                        entity_category=EntityCategory.CONFIG,
                        entity_registry_enabled_default=False,
                    ),
                    attr_options=HA_TO_CYBRO_DISPLAY_MODE_MAP,
                    var_write_req=None,
                    dev_info=dev_info,
                )
            )

    if len(res) > 0:
        return res
    return None


class HiqSelectEntity(HiqEntity, SelectEntity):
    """Defines a HIQ-Home number entity."""

    def __init__(
        self,
        coordinator: HiqDataUpdateCoordinator,
        attr_options: dict[str, int],
        entity_description: HiqSelectEntityDescription | None = None,
        unique_id: str | None = None,
        var_write_req: str | None = None,
        dev_info: DeviceInfo = None,
    ) -> None:
        """Initialize a HIQ-Home select entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = unique_id or entity_description.key
        self._var_write_req = var_write_req
        self._attr_device_info = dev_info

        LOGGER.debug(self._attr_unique_id)
        coordinator.data.add_var(self._attr_unique_id, var_type=VarType.INT)
        self._var_type = VarType.INT
        self._attr_options = list(attr_options)
        self._var_map = attr_options

    @property
    def current_option(self) -> str | None:
        """Return the option."""
        try:
            val_map = {value: key for key, value in self._var_map.items()}
            return val_map[
                self.coordinator.get_value(
                    self._attr_unique_id,
                )
            ]
        except KeyError:
            return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        try:
            desc = self.coordinator.data.vars[self._attr_unique_id].description
        except KeyError:
            desc = "?"
        return {
            ATTR_DESCRIPTION: desc,
        }

    async def async_select_option(self, option: str) -> None:
        """Set new option."""
        if self._var_write_req:
            LOGGER.debug(
                "write value: %s -> %s (%s) (+%s)",
                self._attr_unique_id,
                self._var_map[option],
                str(option),
                self._var_write_req,
            )
            await self.coordinator.cybro.request(
                {
                    self._attr_unique_id: self._var_map[option],
                    self._var_write_req: "1",
                }
            )
        else:
            LOGGER.debug(
                "write value: %s -> %s (%s)",
                self._attr_unique_id,
                self._var_map[option],
                str(option),
            )
            await self.coordinator.cybro.write_var(
                self._attr_unique_id, self._var_map[option]
            )
        await self.coordinator.async_refresh()
