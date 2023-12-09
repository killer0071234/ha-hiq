"""Support for HIQ-Home number."""
from __future__ import annotations

from re import search

from datetime import datetime

from cybro import VarType
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

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
    """Set up HIQ-Home numbers based on a config entry."""
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
) -> list[HiqNumberEntity] | None:
    """Find numbers for thermostat tags in the plc vars.
    eg: c1000.th00_setpoint_idle and so on.
    """
    res: list[HiqNumberEntity] = []

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

        # setpoint idle
        if key in (
            f"{unique_id}_setpoint_idle",
            f"{unique_id}_setpoint_idle_c",
            f"{unique_id}_setpoint_idle_h",
        ):
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                res.append(
                    HiqNumberEntity(
                        coordinator=coordinator,
                        var_name=_format_name(
                            key, f"{unique_id} thermostat setpoint idle"
                        ),
                        unique_id=key,
                        var_description="",
                        var_unit=UnitOfTemperature.CELSIUS,
                        var_type=VarType.FLOAT,
                        attr_device_class=NumberDeviceClass.TEMPERATURE,
                        val_fact=0.1,
                        attr_min_value=0.0,
                        attr_max_value=40.0,
                        var_write_req=get_write_req_th(key, unique_id),
                        enabled=False,
                        dev_info=dev_info,
                    )
                )
        # setpoint offset
        elif key in (
            f"{unique_id}_setpoint_offset",
            f"{unique_id}_setpoint_offset_c",
            f"{unique_id}_setpoint_offset_h",
        ):
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                res.append(
                    HiqNumberEntity(
                        coordinator=coordinator,
                        var_name=_format_name(
                            key, f"{unique_id} thermostat setpoint offset"
                        ),
                        unique_id=key,
                        var_description="",
                        var_unit=UnitOfTemperature.CELSIUS,
                        var_type=VarType.FLOAT,
                        attr_device_class=NumberDeviceClass.TEMPERATURE,
                        attr_entity_category=EntityCategory.CONFIG,
                        val_fact=0.1,
                        attr_min_value=-5.0,
                        attr_max_value=5.0,
                        var_write_req=get_write_req_th(key, unique_id),
                        enabled=False,
                        dev_info=dev_info,
                    )
                )
        # setpoint low
        elif key in (
            f"{unique_id}_setpoint_lo",
            f"{unique_id}_setpoint_lo_c",
            f"{unique_id}_setpoint_lo_h",
        ):
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                res.append(
                    HiqNumberEntity(
                        coordinator=coordinator,
                        var_name=_format_name(
                            key, f"{unique_id} thermostat setpoint low"
                        ),
                        unique_id=key,
                        var_description="",
                        var_unit=UnitOfTemperature.CELSIUS,
                        var_type=VarType.FLOAT,
                        attr_device_class=NumberDeviceClass.TEMPERATURE,
                        attr_entity_category=EntityCategory.CONFIG,
                        val_fact=0.1,
                        attr_min_value=0.0,
                        attr_max_value=40.0,
                        var_write_req=get_write_req_th(key, unique_id),
                        enabled=False,
                        dev_info=dev_info,
                    )
                )
        # setpoint high
        elif key in (
            f"{unique_id}_setpoint_hi",
            f"{unique_id}_setpoint_hi_c",
            f"{unique_id}_setpoint_hi_h",
        ):
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                res.append(
                    HiqNumberEntity(
                        coordinator=coordinator,
                        var_name=_format_name(
                            key, f"{unique_id} thermostat setpoint high"
                        ),
                        unique_id=key,
                        var_description="",
                        var_unit=UnitOfTemperature.CELSIUS,
                        var_type=VarType.FLOAT,
                        attr_device_class=NumberDeviceClass.TEMPERATURE,
                        attr_entity_category=EntityCategory.CONFIG,
                        val_fact=0.1,
                        attr_min_value=0.0,
                        attr_max_value=40.0,
                        var_write_req=get_write_req_th(key, unique_id),
                        enabled=False,
                        dev_info=dev_info,
                    )
                )
        # hysteresis
        elif key in (
            f"{unique_id}_hysteresis",
            f"{unique_id}_hysteresis_c",
            f"{unique_id}_hysteresis_h",
        ):
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                res.append(
                    HiqNumberEntity(
                        coordinator=coordinator,
                        var_name=_format_name(
                            key, f"{unique_id} thermostat hystheresis"
                        ),
                        unique_id=key,
                        var_description="",
                        var_unit=UnitOfTemperature.CELSIUS,
                        var_type=VarType.FLOAT,
                        attr_device_class=NumberDeviceClass.TEMPERATURE,
                        attr_entity_category=EntityCategory.CONFIG,
                        val_fact=0.1,
                        attr_min_value=0.1,
                        attr_max_value=10.0,
                        var_write_req=get_write_req_th(key, unique_id),
                        enabled=False,
                        dev_info=dev_info,
                    )
                )
        # max temp
        elif key == f"{unique_id}_max_temp":
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                res.append(
                    HiqNumberEntity(
                        coordinator=coordinator,
                        var_name=_format_name(
                            key, f"{unique_id} thermostat max temp external"
                        ),
                        unique_id=key,
                        var_description="",
                        var_unit=UnitOfTemperature.CELSIUS,
                        var_type=VarType.FLOAT,
                        attr_device_class=NumberDeviceClass.TEMPERATURE,
                        attr_entity_category=EntityCategory.CONFIG,
                        val_fact=0.1,
                        attr_min_value=0.0,
                        attr_max_value=40.0,
                        var_write_req=get_write_req_th(key, unique_id),
                        enabled=False,
                        dev_info=dev_info,
                    )
                )
        # max time
        elif key in (
            f"{unique_id}_max_time",
            f"{unique_id}_max_time_c",
            f"{unique_id}_max_time_h",
        ):
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                res.append(
                    HiqNumberEntity(
                        coordinator=coordinator,
                        var_name=_format_name(
                            key, f"{unique_id} thermostat activation time max function"
                        ),
                        unique_id=key,
                        var_description="",
                        var_unit=UnitOfTime.SECONDS,
                        var_type=VarType.INT,
                        attr_device_class=NumberDeviceClass.DURATION,
                        attr_entity_category=EntityCategory.CONFIG,
                        val_fact=1.0,
                        display_precision=0,
                        attr_min_value=0,
                        attr_max_value=3600,
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
) -> list[HiqNumberEntity] | None:
    """Find and add HVAC tags in the plc vars.
    eg: c1000.outdoor_temperature and so on.
    """
    res: list[HiqNumberEntity] = []

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

        # get hvac settings
        if key in (
            f"{unique_id}.setpoint_idle_heating",
            f"{unique_id}.setpoint_lo_heating",
            f"{unique_id}.setpoint_hi_heating",
            f"{unique_id}.setpoint_idle_cooling",
            f"{unique_id}.setpoint_lo_cooling",
            f"{unique_id}.setpoint_hi_cooling",
        ):
            res.append(
                HiqNumberEntity(
                    coordinator=coordinator,
                    var_name=_format_name(key, f"{unique_id} HVAC", unique_id),
                    unique_id=key,
                    var_description="",
                    var_unit=UnitOfTemperature.CELSIUS,
                    var_type=VarType.FLOAT,
                    attr_device_class=NumberDeviceClass.TEMPERATURE,
                    val_fact=0.1,
                    attr_min_value=0.0,
                    attr_max_value=40.0,
                    enabled=False,
                    dev_info=dev_info,
                )
            )

    if len(res) > 0:
        return res
    return None


class HiqNumberEntity(HiqEntity, NumberEntity):
    """Defines a HIQ-Home number entity."""

    _var_type: VarType = VarType.INT
    _val_fact: float = 1.0

    def __init__(
        self,
        coordinator: HiqDataUpdateCoordinator,
        var_name: str = "",
        unique_id: str | None = None,
        var_description: str = "",
        var_unit: str | None = None,
        var_type: VarType = VarType.INT,
        attr_device_class: NumberDeviceClass = None,
        mode: NumberMode = NumberMode.BOX,
        val_fact: float = 1.0,
        display_precision: int = 1,
        attr_min_value: float = 0.0,
        attr_max_value: float = 100.0,
        var_write_req: str | None = None,
        attr_entity_category: EntityCategory | None = None,
        enabled: bool = True,
        dev_info: DeviceInfo = None,
    ) -> None:
        """Initialize a HIQ-Home number entity."""
        super().__init__(coordinator=coordinator)
        if var_name == "":
            return
        self._attr_native_unit_of_measurement = var_unit
        self._unique_id = var_name
        self._attr_unique_id = unique_id or var_name
        self._attr_name = var_description if var_description != "" else var_name
        self._var_write_req = var_write_req
        self._state = None
        self._attr_device_info = dev_info
        self._attr_entity_category = attr_entity_category
        self._attr_device_class = attr_device_class
        self._attr_mode = mode

        if enabled is False:
            self._attr_entity_registry_enabled_default = False
        LOGGER.debug(self._attr_unique_id)
        coordinator.data.add_var(self._attr_unique_id, var_type=var_type)
        self._var_type = var_type
        self._val_fact = val_fact
        self._attr_suggested_display_precision = display_precision
        self._attr_native_step = self._val_fact
        self._attr_native_min_value = attr_min_value
        self._attr_native_max_value = attr_max_value

    @property
    def native_value(self) -> datetime | StateType | None:
        """Return the state of the number."""
        return self.coordinator.get_value(
            self._attr_unique_id,
            self._val_fact,
            self._attr_suggested_display_precision,
        )

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

    async def async_set_native_value(self, value: float) -> None:
        """Set new number value."""
        new_val = value * (1.0 / self._val_fact)
        if self._var_type == VarType.INT:
            new_val = int(new_val)
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
