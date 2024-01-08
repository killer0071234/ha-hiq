"""Support for HIQ-Home button."""
from __future__ import annotations

from re import search, sub
from dataclasses import dataclass


from cybro import VarType
from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    AREA_CLIMATE,
    ATTR_DESCRIPTION,
    CONF_IGNORE_GENERAL_ERROR,
    DOMAIN,
    LOGGER,
    MANUFACTURER,
)
from .coordinator import HiqDataUpdateCoordinator
from .light import is_general_error_ok
from .models import HiqEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HIQ-Home select based on a config entry."""
    coordinator: HiqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    ignore_general_error = entry.options.get(CONF_IGNORE_GENERAL_ERROR, False)

    hvac_tags = add_hvac_tags(
        coordinator,
        ignore_general_error,
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
    ignore_general_error: bool,
) -> list[HiqButtonEntity] | None:
    """Find and add HVAC tags in the plc vars.
    eg: c1000.outdoor_temperature and so on.
    """
    res: list[HiqButtonEntity] = []

    # find all thermostats
    thermostats = []
    for key in coordinator.data.plc_info.plc_vars:
        # identifier is cNAD.thNR
        grp = search(r"c\d+\.th\d+", key)
        if grp:
            thermostats.append(grp.group())
    thermostats = list(dict.fromkeys(thermostats))
    if len(thermostats) == 0:
        return None

    # find all hvac tags
    hvacs = []
    for key in coordinator.data.plc_info.plc_vars:
        # identifier is cNAD.thNR
        grp = search(r"c\d+\.hvac_.*", key)
        if grp:
            hvacs.append(grp.group())
    hvacs = list(dict.fromkeys(hvacs))
    if len(hvacs) == 0:
        return None

    # generate device info
    unique_id = hvacs[0]
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

    # check for existing global parameter
    for hvac in hvacs:
        if hvac in (
            f"{unique_id}.hvac_temperature_source",
            f"{unique_id}.hvac_display_mode",
            f"{unique_id}.hvac_fan_option_b01",
            f"{unique_id}.hvac_fan_option_b02",
            f"{unique_id}.hvac_fan_option_b03",
            f"{unique_id}.hvac_fan_option_b04",
        ):
            has_para_for_thermostat = True
    if has_para_for_thermostat is None:
        return None

    # add config buttons for active thermostats
    for thermostat in thermostats:
        unique_id = thermostat
        # identifier is cNAD.thNR
        grp = search(r"c\d+\.th\d+", thermostat)
        if grp:
            unique_id = grp.group()
        dev_info = DeviceInfo(
            identifiers={(coordinator.cybro.nad, f"{unique_id} thermostat")},
            manufacturer=MANUFACTURER,
            name=f"{unique_id} thermostat",
            suggested_area=AREA_CLIMATE,
            via_device=(DOMAIN, coordinator.cybro.nad),
        )

        is_ge_ok = is_general_error_ok(coordinator, f"{thermostat}_general_error")

        if is_ge_ok or ignore_general_error:
            # config 1 request
            key = f"{thermostat}_config1_req"
            if key in coordinator.data.plc_info.plc_vars:
                res.append(
                    HiqButtonEntity(
                        coordinator=coordinator,
                        entity_description=HiqButtonEntityDescription(
                            key=key,
                            translation_key="config1_write_req",
                            entity_category=EntityCategory.CONFIG,
                            entity_registry_enabled_default=False,
                        ),
                        var_value=1,
                        dev_info=dev_info,
                    )
                )
            # read back options
            key = f"{thermostat}_options_back_req"
            if key in coordinator.data.plc_info.plc_vars:
                res.append(
                    HiqButtonEntity(
                        coordinator=coordinator,
                        entity_description=HiqButtonEntityDescription(
                            key=key,
                            translation_key="config1_read_req",
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
        self._state = None
        self._attr_device_info = dev_info
        self._var_value = var_value

        LOGGER.debug(self._attr_unique_id)
        coordinator.data.add_var(self._attr_unique_id, var_type=VarType.INT)
        self._var_type = VarType.INT

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

    async def async_press(self) -> None:
        """Write Button press to tag."""
        LOGGER.debug(
            "write value: %s -> %s (%s)",
            self._attr_unique_id,
            self._var_value,
        )
        await self.coordinator.cybro.write_var(self._attr_unique_id, self._var_value)
        await self.coordinator.async_refresh()
