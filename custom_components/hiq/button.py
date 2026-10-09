"""Support for HIQ-Home button."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from re import search
from re import sub

from cybro import VarType
from homeassistant.components.button import ButtonEntity
from homeassistant.components.button import ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_DESCRIPTION
from .const import ATTR_VARIABLE
from .const import DOMAIN
from .const import LOGGER
from .coordinator import HiqDataUpdateCoordinator
from .light import is_general_error_ok
from .models import HiqEntity
from .models import thermostat_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HIQ-Home select based on a config entry."""
    coordinator: HiqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    hvac_tags = add_hvac_tags(
        coordinator,
    )
    if hvac_tags is not None:
        async_add_entities(hvac_tags)


@dataclass
class HiqButtonEntityDescription(ButtonEntityDescription):
    """HIQ Button Entity Description."""

    def __post_init__(self):
        """Defaults the translation_key to the sensor key."""
        self.has_entity_name = True
        self.translation_key = (
            self.translation_key
            or sub(r"c\d+\.", "", self.key).replace(".", "_").lower()
        )


def add_hvac_tags(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqButtonEntity] | None:
    """Find and add HVAC tags in the plc vars.
    eg: c1000.outdoor_temperature and so on.
    """
    res: list[HiqButtonEntity] = []

    # find all thermostats, identifier is cNAD.thNR
    thermostats = unique_matches(r"c\d+\.th\d+", coordinator.data.plc_info.plc_vars)
    if len(thermostats) == 0:
        return None

    # find all hvac tags
    hvacs = unique_matches(r"c\d+\.hvac_.*", coordinator.data.plc_info.plc_vars)
    if len(hvacs) == 0:
        return None

    unique_id = hvacs[0]
    # identifier is cNAD, taken from the last plc var
    grp = search(r"c\d+", next(reversed(coordinator.data.plc_info.plc_vars)))
    if grp:
        unique_id = grp.group()

    # check for existing global parameter
    global_params = (
        f"{unique_id}.hvac_temperature_source",
        f"{unique_id}.hvac_display_mode",
        f"{unique_id}.hvac_fan_option_b01",
        f"{unique_id}.hvac_fan_option_b02",
        f"{unique_id}.hvac_fan_option_b03",
        f"{unique_id}.hvac_fan_option_b04",
    )
    if not any(hvac in global_params for hvac in hvacs):
        return None

    # add config buttons for active thermostats
    for thermostat in thermostats:
        if not is_general_error_ok(coordinator, f"{thermostat}_general_error"):
            continue
        dev_info = thermostat_device_info(coordinator, thermostat)
        for suffix, translation_key in (
            ("config1_req", "config1_write_req"),
            ("options_back_req", "config1_read_req"),
        ):
            key = f"{thermostat}_{suffix}"
            if key in coordinator.data.plc_info.plc_vars:
                res.append(
                    HiqButtonEntity(
                        coordinator=coordinator,
                        entity_description=HiqButtonEntityDescription(
                            key=key,
                            translation_key=translation_key,
                            entity_category=EntityCategory.CONFIG,
                            entity_registry_enabled_default=False,
                        ),
                        var_value=1,
                        dev_info=dev_info,
                    )
                )

    if len(res) > 0:
        return res
    return None


def unique_matches(pattern: str, keys: Iterable[str]) -> list[str]:
    """Return the distinct matches of pattern in keys, in order of appearance."""
    return list(
        dict.fromkeys(match.group() for key in keys if (match := search(pattern, key)))
    )


class HiqButtonEntity(HiqEntity, ButtonEntity):
    """Defines a HIQ-Home button entity."""

    def __init__(
        self,
        coordinator: HiqDataUpdateCoordinator,
        entity_description: HiqButtonEntityDescription | None = None,
        unique_id: str | None = None,
        var_value: int = 1,
        dev_info: DeviceInfo = None,
    ) -> None:
        """Initialize a HIQ-Home button entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = unique_id or entity_description.key
        self._attr_device_info = dev_info
        self._var_value = var_value

        LOGGER.debug(self._attr_unique_id)
        coordinator.data.add_var(self._attr_unique_id, var_type=VarType.INT)

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

    async def async_press(self) -> None:
        """Write Button press to tag."""
        LOGGER.debug(
            "write value: %s -> %s",
            self._attr_unique_id,
            self._var_value,
        )
        await self.coordinator.cybro.write_var(self._attr_unique_id, self._var_value)
        await self.coordinator.async_refresh()
