"""Support for HIQ-Home select."""
from __future__ import annotations

from re import search


from cybro import VarType
from homeassistant.components.select import (
    SelectEntity,
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
    MANUFACTURER_URL,
    DEVICE_DESCRIPTION,
)
from .coordinator import HiqDataUpdateCoordinator
from .light import is_general_error_ok
from .models import HiqEntity
from . import get_write_req_th

HA_TO_CYBRO_TEMP_SOURCE_MAP = {
    "internal sensor": 0,
    "external sensor": 1,
    "remote sensor": 2,
}

HA_TO_CYBRO_DISPLAY_MODE_MAP = {
    "nothing": 0,
    "---": 1,
    "temperature": 2,
}

HA_TO_CYBRO_HVAC_MODE_MAP = {
    "none": 0,
    "heating": 1,
    "cooling": 2,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HIQ-Home select based on a config entry."""
    coordinator: HiqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    ignore_general_error = entry.options.get(CONF_IGNORE_GENERAL_ERROR, False)

    th_tags = add_th_tags(
        coordinator,
        ignore_general_error,
    )
    if th_tags is not None:
        async_add_entities(th_tags)

    hvac_tags = add_hvac_tags(
        coordinator,
    )
    if hvac_tags is not None:
        async_add_entities(hvac_tags)


def add_th_tags(
    coordinator: HiqDataUpdateCoordinator,
    add_all: bool = False,
) -> list[HiqSelectEntity] | None:
    """Find select for thermostat tags in the plc vars.
    eg: c1000.th00_window_enable and so on.
    """
    res: list[HiqSelectEntity] = []

    def _format_name(key: str, name: str) -> str:
        """Append cool or heat to name."""
        if key.endswith("_h"):
            return f"{name} heating"
        if key.endswith("_c"):
            return f"{name} cooling"
        return name

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

        # temperature source
        if key in (f"{unique_id}_temperature_source",):
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                res.append(
                    HiqSelectEntity(
                        coordinator=coordinator,
                        var_name=_format_name(
                            key, f"{unique_id} thermostat temperature source"
                        ),
                        unique_id=key,
                        var_description="",
                        attr_options=HA_TO_CYBRO_TEMP_SOURCE_MAP,
                        attr_entity_category=EntityCategory.CONFIG,
                        var_write_req=get_write_req_th(key, unique_id),
                        enabled=False,
                        dev_info=dev_info,
                    )
                )
        # display mode
        elif key in (f"{unique_id}_display_mode",):
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                res.append(
                    HiqSelectEntity(
                        coordinator=coordinator,
                        var_name=_format_name(
                            key, f"{unique_id} thermostat display mode"
                        ),
                        unique_id=key,
                        var_description="",
                        attr_options=HA_TO_CYBRO_DISPLAY_MODE_MAP,
                        attr_entity_category=EntityCategory.CONFIG,
                        var_write_req=get_write_req_th(key, unique_id),
                        enabled=False,
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

    def _format_name(key: str, name: str, unique_id: str) -> str:
        """Format key to name."""
        subpart = key.replace(unique_id, "")
        return name + subpart.replace("_", " ").replace(".", " ")

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
                    var_name=_format_name(
                        key,
                        f"{unique_id} HVAC",
                        unique_id,
                    ),
                    unique_id=key,
                    var_description="",
                    var_write_req=None,
                    attr_options=HA_TO_CYBRO_HVAC_MODE_MAP,
                    attr_entity_category=EntityCategory.CONFIG,
                    enabled=False,
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
        var_name: str = "",
        unique_id: str | None = None,
        var_description: str = "",
        var_write_req: str | None = None,
        attr_entity_category: EntityCategory | None = None,
        enabled: bool = True,
        dev_info: DeviceInfo = None,
    ) -> None:
        """Initialize a HIQ-Home select entity."""
        super().__init__(coordinator=coordinator)
        if var_name == "":
            return
        self._unique_id = var_name
        self._attr_unique_id = unique_id or var_name
        self._attr_name = var_description if var_description != "" else var_name
        self._var_write_req = var_write_req
        self._state = None
        self._attr_device_info = dev_info
        self._attr_entity_category = attr_entity_category

        if enabled is False:
            self._attr_entity_registry_enabled_default = False
        LOGGER.debug(self._attr_unique_id)
        coordinator.data.add_var(self._attr_unique_id, var_type=VarType.INT)
        self._var_type = VarType.INT
        self._attr_options = list(attr_options)
        self._var_map = attr_options

    @property
    def device_info(self):
        """Return the device info."""
        if self._attr_device_info is not None:
            return self._attr_device_info
        return DeviceInfo(
            identifiers={(DOMAIN, self.platform.config_entry.unique_id)},
            manufacturer=MANUFACTURER,
            configuration_url=MANUFACTURER_URL,
            name=f"PLC {self.coordinator.cybro.nad}",
            model=DEVICE_DESCRIPTION,
        )

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
            desc = self._attr_name
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
