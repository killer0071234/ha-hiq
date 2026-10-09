"""Support for HIQ-Home number."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from re import search
from re import sub

from cybro import VarType
from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.number import NumberEntity
from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.number import NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import get_write_req_th
from .const import ATTR_DESCRIPTION
from .const import ATTR_VARIABLE
from .const import DOMAIN
from .const import LOGGER
from .coordinator import HiqDataUpdateCoordinator
from .light import is_general_error_ok
from .models import HiqEntity
from .models import thermostat_device_info
from .models import hvac_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HIQ-Home numbers based on a config entry."""
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


@dataclass
class HiqNumberEntityDescription(NumberEntityDescription):
    """HIQ Number Entity Description."""

    def __post_init__(self):
        """Defaults the translation_key to the number key."""
        self.has_entity_name = True
        self.translation_key = (
            self.translation_key
            or sub(r"c\d+\.", "", self.key).replace(".", "_").lower()
        )


# thermostat temperature numbers: name -> (min, max, entity category)
TH_TEMPERATURE_NUMBERS: dict[str, tuple[float, float, EntityCategory | None]] = {
    "setpoint_idle": (0.0, 40.0, None),
    "setpoint_offset": (-5.0, 5.0, EntityCategory.CONFIG),
    "setpoint_lo": (0.0, 40.0, EntityCategory.CONFIG),
    "setpoint_hi": (0.0, 40.0, EntityCategory.CONFIG),
    "hysteresis": (0.1, 10.0, EntityCategory.CONFIG),
    "max_temp": (0.0, 40.0, EntityCategory.CONFIG),
}
# names that also exist for cooling (_c) and heating (_h)
TH_NUMBERS_WITH_MODES = (
    "setpoint_idle",
    "setpoint_offset",
    "setpoint_lo",
    "setpoint_hi",
    "hysteresis",
    "max_time",
)


def _th_number_name(name: str) -> str:
    """Return the number name without the cooling / heating suffix."""
    for suffix in ("_c", "_h"):
        base = name.removesuffix(suffix)
        if base != name and base in TH_NUMBERS_WITH_MODES:
            return base
    return name


def add_th_tags(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqNumberEntity] | None:
    """Find numbers for thermostat tags in the plc vars.
    eg: c1000.th00_setpoint_idle and so on.
    """
    res: list[HiqNumberEntity] = []

    for key in coordinator.data.plc_info.plc_vars:
        # identifier is cNAD.thNR
        grp = search(r"c\d+\.th\d+", key)
        if not grp or not key.startswith(f"{grp.group()}_"):
            continue
        unique_id = grp.group()
        translation_key = key.removeprefix(f"{unique_id}_")
        name = _th_number_name(translation_key)

        if name in TH_TEMPERATURE_NUMBERS:
            min_value, max_value, entity_category = TH_TEMPERATURE_NUMBERS[name]
            description = HiqNumberEntityDescription(
                key=key,
                translation_key=translation_key,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=NumberDeviceClass.TEMPERATURE,
                entity_category=entity_category,
                native_min_value=min_value,
                native_max_value=max_value,
                entity_registry_enabled_default=False,
            )
            var_type, val_fact, display_precision = VarType.FLOAT, 0.1, 1
        elif name == "max_time":
            description = HiqNumberEntityDescription(
                key=key,
                translation_key=translation_key,
                native_unit_of_measurement=UnitOfTime.SECONDS,
                device_class=NumberDeviceClass.DURATION,
                entity_category=EntityCategory.CONFIG,
                native_min_value=0,
                native_max_value=3600,
                entity_registry_enabled_default=False,
            )
            var_type, val_fact, display_precision = VarType.INT, 1.0, 0
        else:
            continue

        if not is_general_error_ok(coordinator, key):
            continue
        res.append(
            HiqNumberEntity(
                coordinator=coordinator,
                entity_description=description,
                var_type=var_type,
                val_fact=val_fact,
                display_precision=display_precision,
                var_write_req=get_write_req_th(key, unique_id),
                dev_info=thermostat_device_info(coordinator, unique_id),
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

    # find different hvac related vars
    for key in coordinator.data.plc_info.plc_vars:
        # identifier is cNAD
        grp = search(r"c\d+", key)
        if not grp or not key.startswith(f"{grp.group()}."):
            continue
        unique_id = grp.group()
        name = key.removeprefix(f"{unique_id}.")
        if name not in (
            "setpoint_idle_heating",
            "setpoint_lo_heating",
            "setpoint_hi_heating",
            "setpoint_idle_cooling",
            "setpoint_lo_cooling",
            "setpoint_hi_cooling",
        ):
            continue
        res.append(
            HiqNumberEntity(
                coordinator=coordinator,
                entity_description=HiqNumberEntityDescription(
                    key=key,
                    translation_key=name,
                    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                    device_class=NumberDeviceClass.TEMPERATURE,
                    entity_category=EntityCategory.CONFIG,
                    native_min_value=0.0,
                    native_max_value=40.0,
                    entity_registry_enabled_default=False,
                ),
                var_type=VarType.FLOAT,
                val_fact=0.1,
                dev_info=hvac_device_info(coordinator, unique_id),
            )
        )

    if len(res) > 0:
        return res
    return None


class HiqNumberEntity(HiqEntity, NumberEntity):
    """Defines a HIQ-Home number entity."""

    _val_fact: float = 1.0

    def __init__(
        self,
        coordinator: HiqDataUpdateCoordinator,
        entity_description: HiqNumberEntityDescription | None = None,
        unique_id: str | None = None,
        var_type: VarType = VarType.INT,
        mode: NumberMode = NumberMode.BOX,
        val_fact: float = 1.0,
        display_precision: int = 1,
        var_write_req: str | None = None,
        dev_info: DeviceInfo = None,
    ) -> None:
        """Initialize a HIQ-Home number entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = unique_id or entity_description.key
        self._var_write_req = var_write_req
        self._attr_device_info = dev_info
        self._attr_mode = mode

        LOGGER.debug(self._attr_unique_id)
        coordinator.data.add_var(self._attr_unique_id, var_type=var_type)
        self._val_fact = val_fact
        self._attr_suggested_display_precision = display_precision
        self.entity_description.native_step = self._val_fact

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
            desc = "?"
        return {
            ATTR_DESCRIPTION: desc,
            ATTR_VARIABLE: self._attr_unique_id,
        }

    async def async_set_native_value(self, value: float) -> None:
        """Set new number value."""
        # the controller stores scaled values as integer (e.g. 0.1 °C steps)
        new_val = round(value / self._val_fact)
        if self._var_write_req:
            LOGGER.debug(
                "write value: %s -> %s (+%s)",
                self._attr_unique_id,
                new_val,
                self._var_write_req,
            )
            await self.coordinator.cybro.request(
                {
                    self._attr_unique_id: str(new_val),
                    self._var_write_req: "1",
                }
            )
        else:
            LOGGER.debug("write value: %s -> %s", self._attr_unique_id, new_val)
            await self.coordinator.cybro.write_var(self._attr_unique_id, new_val)
        await self.coordinator.async_refresh()
