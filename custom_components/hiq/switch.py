"""Support for HIQ-Home switch."""
from __future__ import annotations

from dataclasses import dataclass
from re import search
from re import sub
from typing import Generic
from typing import TypeVar

from cybro import VarType
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import get_write_req_th
from .const import AREA_CLIMATE
from .const import ATTR_DESCRIPTION
from .const import ATTR_VARIABLE
from .const import DOMAIN
from .const import LOGGER
from .const import MANUFACTURER
from .coordinator import HiqDataUpdateCoordinator
from .light import is_general_error_ok
from .models import HiqEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HIQ-Home switch based on a config entry."""
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
class HiqSwitchEntityDescription(Generic[T], SwitchEntityDescription):
    """HIQ Switch Entity Description."""

    def __post_init__(self):
        """Defaults the translation_key to the sensor key."""
        self.has_entity_name = True
        self.translation_key = (
            self.translation_key
            or sub(r"c\d+\.", "", self.key).replace(".", "_").lower()
        )


def add_th_tags(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqSwitchEntity] | None:
    """Find switch for thermostat tags in the plc vars.
    eg: c1000.th00_window_enable and so on.
    """
    res: list[HiqSwitchEntity] = []

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

        # window enable
        if key in (f"{unique_id}_window_enable",):
            if is_general_error_ok(coordinator, key):
                res.append(
                    HiqSwitchEntity(
                        coordinator=coordinator,
                        entity_description=HiqSwitchEntityDescription(
                            key=key,
                            translation_key=key.removeprefix(f"{unique_id}_"),
                            entity_category=EntityCategory.CONFIG,
                            entity_registry_enabled_default=False,
                        ),
                        var_write_req=get_write_req_th(key, unique_id),
                        dev_info=dev_info,
                    )
                )
        # demand enable
        elif key in (f"{unique_id}_demand_enable",):
            if is_general_error_ok(coordinator, key):
                res.append(
                    HiqSwitchEntity(
                        coordinator=coordinator,
                        entity_description=HiqSwitchEntityDescription(
                            key=key,
                            translation_key=key.removeprefix(f"{unique_id}_"),
                            entity_category=EntityCategory.CONFIG,
                            entity_registry_enabled_default=False,
                        ),
                        var_write_req=get_write_req_th(key, unique_id),
                        dev_info=dev_info,
                    )
                )

    if len(res) > 0:
        return res
    return None


def add_hvac_tags(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqSwitchEntity] | None:
    """Find and add HVAC tags in the plc vars.
    eg: c1000.outdoor_temperature and so on.
    """
    res: list[HiqSwitchEntity] = []

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

        # get temperature enables(s)
        if key in (
            f"{unique_id}.outdoor_temperature_enable",
            f"{unique_id}.wall_temperature_enable",
            f"{unique_id}.water_temperature_enable",
            f"{unique_id}.auxilary_temperature_enable",
            f"{unique_id}.auto_limits_enable",
        ):
            res.append(
                HiqSwitchEntity(
                    coordinator=coordinator,
                    entity_description=HiqSwitchEntityDescription(
                        key=key,
                        translation_key=key.removeprefix(f"{unique_id}."),
                        entity_category=EntityCategory.CONFIG,
                        entity_registry_enabled_default=False,
                    ),
                    var_write_req=None,
                    dev_info=dev_info,
                )
            )
        # fan option
        elif key in (
            f"{unique_id}.hvac_fan_option_b01",
            f"{unique_id}.hvac_fan_option_b02",
            f"{unique_id}.hvac_fan_option_b03",
            f"{unique_id}.hvac_fan_option_b04",
        ):
            res.append(
                HiqSwitchEntity(
                    coordinator=coordinator,
                    entity_description=HiqSwitchEntityDescription(
                        key=key,
                        translation_key=key.removeprefix(f"{unique_id}."),
                        entity_category=EntityCategory.CONFIG,
                        entity_registry_enabled_default=False,
                    ),
                    var_write_req=get_write_req_th(key, unique_id),
                    dev_info=dev_info,
                )
            )

    if len(res) > 0:
        return res
    return None


class HiqSwitchEntity(HiqEntity, SwitchEntity):
    """Defines a HIQ-Home buton entity."""

    def __init__(
        self,
        coordinator: HiqDataUpdateCoordinator,
        entity_description: HiqSwitchEntityDescription | None = None,
        unique_id: str | None = None,
        var_write_req: str | None = None,
        var_invert: bool = False,
        dev_info: DeviceInfo = None,
    ) -> None:
        """Initialize a HIQ-Home button entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = unique_id or entity_description.key
        self._var_write_req = var_write_req
        self._state = None
        self._attr_device_info = dev_info

        LOGGER.debug(self._attr_unique_id)
        coordinator.data.add_var(self._attr_unique_id, var_type=VarType.INT)
        self._var_type = VarType.INT
        self._var_invert = var_invert

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        val = self.coordinator.get_value(self._attr_unique_id, 1.0, 0, None)
        if val is None:
            return None
        if self._var_invert:
            return int(val) == 0
        return val

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        new_val = 1 if self._var_invert else 0
        if self._var_write_req:
            LOGGER.debug(
                "write value: %s -> %s (+%s)",
                self._attr_unique_id,
                str(new_val),
                self._var_write_req,
            )
            await self.coordinator.cybro.request(
                {
                    self._attr_unique_id: str(new_val),
                    self._var_write_req: "1",
                }
            )
        else:
            LOGGER.debug("write value: %s -> %s", self._attr_unique_id, str(new_val))
            await self.coordinator.cybro.write_var(self._attr_unique_id, new_val)
        await self.coordinator.async_refresh()

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        new_val = 0 if self._var_invert else 1
        if self._var_write_req:
            LOGGER.debug(
                "write value: %s -> %s (+%s)",
                self._attr_unique_id,
                str(new_val),
                self._var_write_req,
            )
            await self.coordinator.cybro.request(
                {
                    self._attr_unique_id: str(new_val),
                    self._var_write_req: "1",
                }
            )
        else:
            LOGGER.debug("write value: %s -> %s", self._attr_unique_id, str(new_val))
            await self.coordinator.cybro.write_var(self._attr_unique_id, new_val)
        await self.coordinator.async_refresh()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        try:
            desc = self.coordinator.data.vars[self._attr_unique_id].description
        except KeyError:
            desc = "?"
        return {
            ATTR_DESCRIPTION: desc,
            ATTR_VARIABLE: self._attr_unique_id,
        }
