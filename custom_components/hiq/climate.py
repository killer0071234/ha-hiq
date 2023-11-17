"""Support for HIQ-Home climate device."""
from __future__ import annotations

from re import search
from typing import Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    UnitOfTemperature,
)

from .const import (
    AREA_CLIMATE,
    CONF_IGNORE_GENERAL_ERROR,
    DOMAIN,
    LOGGER,
    ATTR_FLOOR_TEMP,
    ATTR_SETPOINT_IDLE,
    ATTR_SETPOINT_ACTIVE,
    ATTR_SETPOINT_OFFSET,
    MANUFACTURER,
)
from .coordinator import HiqDataUpdateCoordinator
from .models import HiqEntity
from .light import is_general_error_ok

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE

SUPPORT_MODES_HEAT = [HVACMode.OFF, HVACMode.HEAT]
SUPPORT_MODES_COOL = [HVACMode.OFF, HVACMode.COOL]

HA_TO_CYBRO_HVAC_HEAT_MAP = {
    HVACMode.OFF: 0,
    HVACMode.HEAT: 1,
}
CYBRO_TO_HA_HVAC_HEAT_MAP = {
    value: key for key, value in HA_TO_CYBRO_HVAC_HEAT_MAP.items()
}

HA_TO_CYBRO_HVAC_COOL_MAP = {
    HVACMode.OFF: 0,
    HVACMode.COOL: 1,
}
CYBRO_TO_HA_HVAC_COOL_MAP = {
    value: key for key, value in HA_TO_CYBRO_HVAC_COOL_MAP.items()
}

HA_TO_CYBRO_HVAC_MODE_MAP = {
    HVACMode.OFF: 0,
    HVACMode.HEAT: 1,
    HVACMode.COOL: 2,
}
CYBRO_TO_HA_HVAC_MODE_MAP = {
    value: key for key, value in HA_TO_CYBRO_HVAC_MODE_MAP.items()
}

CYBRO_TO_HA_HVAC_ACTION_COOL_MAP = {
    HVACAction.IDLE: 0,
    HVACAction.COOLING: 1,
}
CYBRO_TO_HA_HVAC_ACTION_COOL_MAP = {
    value: key for key, value in CYBRO_TO_HA_HVAC_ACTION_COOL_MAP.items()
}


CYBRO_TO_HA_HVAC_ACTION_HEAT_MAP = {
    HVACAction.IDLE: 0,
    HVACAction.HEATING: 1,
}
CYBRO_TO_HA_HVAC_ACTION_HEAT_MAP = {
    value: key for key, value in CYBRO_TO_HA_HVAC_ACTION_HEAT_MAP.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    variable_name: str = "",
) -> None:
    """Set up a HIQ climate device based on a config entry."""
    coordinator: HiqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    ignore_general_error = entry.options.get(CONF_IGNORE_GENERAL_ERROR, False)

    thermostats = find_thermostats(
        coordinator,
        ignore_general_error,
    )
    if thermostats is not None:
        async_add_entities(thermostats)


def find_thermostats(
    coordinator: HiqDataUpdateCoordinator,
    add_all: bool = False,
) -> list[HiqThermostat] | None:
    """Find system tags in the plc vars.
    eg: c1000.th00_ and so on.
    """
    res: list[HiqThermostat] = []

    # find thermostats (general_error)
    for key in coordinator.data.plc_info.plc_vars:
        if search(r"c\d+\.th\d+_general_error", key):
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                unique_id = key
                # identifier is cNAD.thNR
                grp = search(r"c\d+\.th\d+", key)
                if grp:
                    unique_id = grp.group()

                res.append(
                    HiqThermostat(
                        coordinator,
                        unique_id,
                    )
                )

    if len(res) > 0:
        return res
    return None


class HiqThermostat(HiqEntity, ClimateEntity):
    """Representation a Hiq thermostat."""

    _attr_hvac_modes = SUPPORT_MODES_HEAT
    _attr_hvac_mode = HVACMode.AUTO
    _attr_supported_features = SUPPORT_FLAGS
    _attr_target_temperature_step = PRECISION_TENTHS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: HiqDataUpdateCoordinator,
        context: Any = None,
    ) -> None:
        """Init of hiq thermostat."""
        super().__init__(coordinator, context)

        # remember the variable prefix eg: c10000.th00
        self._prefix = context
        var_names = self._prefix.split(".")
        self._nad = var_names[0]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._prefix)},
            name=cast(str | None, f"{self._prefix} thermostat"),
            manufacturer=MANUFACTURER,
            suggested_area=AREA_CLIMATE,
            via_device=(DOMAIN, coordinator.cybro.nad),
        )
        self._attr_name = f"{self._prefix} thermostat"
        self._attr_unique_id = f"{self._prefix}_thermostat"

        # add tags for thermostat to coordinator
        coordinator.data.add_var(f"{self._prefix}_active")
        coordinator.data.add_var(f"{self._prefix}_output")
        coordinator.data.add_var(f"{self._prefix}_setpoint_lo")
        coordinator.data.add_var(f"{self._prefix}_setpoint_hi")
        coordinator.data.add_var(f"{self._prefix}_temperature")
        coordinator.data.add_var(f"{self._prefix}_floor_tmp")
        coordinator.data.add_var(f"{self._prefix}_humidity")
        coordinator.data.add_var(f"{self._prefix}_setpoint")
        coordinator.data.add_var(f"{self._prefix}_setpoint_idle")
        coordinator.data.add_var(f"{self._prefix}_setpoint_offset")
        coordinator.data.add_var(f"{self._prefix}_setpoint_active")
        coordinator.data.add_var(f"{self._nad}.hvac_mode")

    def _get_value(
        self,
        tag: str,
        factor: float = 1.0,
        precision: int = 0,
        def_val: int | float | None = None,
    ) -> int | float | None:
        """Return a single Tag Value."""
        res = self.coordinator.data.vars.get(tag, None)
        if res is None:
            return def_val
        if res.value == "?" or res.value is None:
            LOGGER.debug("got unknown value for %s", str(tag))
            return def_val
        if factor == 1.0:
            LOGGER.debug("value for %s -> %s", str(tag), str(res.value))
            return int(res.value)
        if factor != 1.0:
            converted_numerical_value = float(res.value.replace(",", "")) * factor
            value = f"{converted_numerical_value:z.{precision}f}"
            LOGGER.debug(
                "value for %s -> %s",
                str(tag),
                str(value),
            )
            return float(value)

        return res.value

    @property
    def current_temperature(self) -> float | None:
        """Return the reported current temperature for the device."""
        return self._get_value(f"{self._prefix}_temperature", 0.1, 1)

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        if (humidity := self._get_value(f"{self._prefix}_humidity", 1.0, 0)) is None:
            return None
        if humidity > 0:
            return humidity
        return None

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the hvac action."""
        mode = CYBRO_TO_HA_HVAC_MODE_MAP[
            self._get_value(f"{self._nad}.hvac_mode", def_val=0)
        ]
        if mode == HVACMode.HEAT:
            return CYBRO_TO_HA_HVAC_ACTION_HEAT_MAP[
                self._get_value(f"{self._prefix}_output", def_val=0)
            ]
        if mode == HVACMode.COOL:
            return CYBRO_TO_HA_HVAC_ACTION_COOL_MAP[
                self._get_value(f"{self._prefix}_output", def_val=0)
            ]
        return HVACAction.OFF

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature for the device."""
        return self._get_value(f"{self._prefix}_setpoint", 0.1, 1)

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        return self._get_value(f"{self._prefix}_setpoint_lo", 0.1, 1, 5.0)

    @property
    def target_temperature_high(self):
        """Return the higher bound temperature we try to reach."""
        return self._get_value(f"{self._prefix}_setpoint_hi", 0.1, 1, 5.0)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode for the device."""
        mode = CYBRO_TO_HA_HVAC_MODE_MAP[
            self._get_value(f"{self._nad}.hvac_mode", def_val=0)
        ]
        if mode == HVACMode.HEAT:
            self._attr_hvac_modes = SUPPORT_MODES_HEAT
            return CYBRO_TO_HA_HVAC_HEAT_MAP[
                self._get_value(f"{self._prefix}_active", def_val=0)
            ]
        self._attr_hvac_modes = SUPPORT_MODES_COOL
        return CYBRO_TO_HA_HVAC_COOL_MAP[
            self._get_value(f"{self._prefix}_active", def_val=0)
        ]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        data = {}
        if floor_tmp := self._get_value(f"{self._prefix}_floor_tmp", 0.1, 1) or None:
            data[ATTR_FLOOR_TEMP] = floor_tmp
        if (
            setp_idle := self._get_value(f"{self._prefix}_setpoint_idle", 0.1, 1)
            or None
        ):
            data[ATTR_SETPOINT_IDLE] = setp_idle
        if (
            setp_act := self._get_value(f"{self._prefix}_setpoint_active", 0.1, 1)
            or None
        ):
            data[ATTR_SETPOINT_ACTIVE] = setp_act
        if (
            setp_off := self._get_value(f"{self._prefix}_setpoint_offset", 0.1, 1)
            or None
        ):
            data[ATTR_SETPOINT_OFFSET] = setp_off
        return data

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode to device."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.cybro.write_var(f"{self._prefix}_active", "0")
        else:
            await self.coordinator.cybro.write_var(f"{self._prefix}_active", "1")
        await self.coordinator.async_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        await self.coordinator.cybro.write_var(
            f"{self._prefix}_setpoint", int(temperature * 10.0)
        )
        await self.coordinator.async_refresh()
