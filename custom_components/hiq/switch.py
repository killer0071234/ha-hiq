"""Support for HIQ-Home switch."""
from __future__ import annotations

from re import search


from cybro import VarType
from homeassistant.components.switch import (
    SwitchEntity,
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
from . import get_write_req_th


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HIQ-Home switch based on a config entry."""
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
) -> list[HiqSwitchEntity] | None:
    """Find switch for thermostat tags in the plc vars.
    eg: c1000.th00_window_enable and so on.
    """
    res: list[HiqSwitchEntity] = []

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

        # window enable
        if key in (f"{unique_id}_window_enable",):
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                res.append(
                    HiqSwitchEntity(
                        coordinator=coordinator,
                        var_name=_format_name(
                            key, f"{unique_id} thermostat window switch enable"
                        ),
                        unique_id=key,
                        var_description="",
                        var_write_req=get_write_req_th(key, unique_id),
                        attr_entity_category=EntityCategory.CONFIG,
                        enabled=False,
                        dev_info=dev_info,
                    )
                )
        # demand enable
        elif key in (f"{unique_id}_demand_enable",):
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                res.append(
                    HiqSwitchEntity(
                        coordinator=coordinator,
                        var_name=_format_name(
                            key, f"{unique_id} thermostat demand enable"
                        ),
                        unique_id=key,
                        var_description="",
                        var_write_req=get_write_req_th(key, unique_id),
                        attr_entity_category=EntityCategory.CONFIG,
                        enabled=False,
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

    def _format_name(key: str, name: str, unique_id: str) -> str:
        """Format key to name."""
        subpart = key.replace(unique_id, "")
        if subpart.startswith("auto_limits"):
            subpart.replace("automatic setpoint limits")
        elif subpart.endswith("_b04"):
            subpart = subpart.replace("_b04", " speed max")
        subpart = subpart.replace("_b0", " speed auto ")
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
                    var_name=_format_name(
                        key,
                        f"{unique_id} HVAC",
                        unique_id,
                    ),
                    unique_id=key,
                    var_description="",
                    var_write_req=None,
                    attr_entity_category=EntityCategory.CONFIG,
                    enabled=False,
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
                    var_name=_format_name(
                        key,
                        f"{unique_id} HVAC thermostat fan option",
                        unique_id,
                    ),
                    unique_id=key,
                    var_description="",
                    var_write_req=get_write_req_th(key, unique_id),
                    attr_entity_category=EntityCategory.CONFIG,
                    enabled=False,
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
        var_name: str = "",
        unique_id: str | None = None,
        var_description: str = "",
        var_write_req: str | None = None,
        var_invert: bool = False,
        attr_entity_category: EntityCategory | None = None,
        enabled: bool = True,
        dev_info: DeviceInfo = None,
    ) -> None:
        """Initialize a HIQ-Home button entity."""
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
            desc = self._attr_name
        return {
            ATTR_DESCRIPTION: desc,
        }
