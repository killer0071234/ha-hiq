"""Support for HIQ-Home climate device."""
from __future__ import annotations

from re import search
from typing import Any

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
from homeassistant.components.climate.const import (
    PRESET_COMFORT,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    UnitOfTemperature,
)

from .const import (
    AREA_CLIMATE,
    DOMAIN,
    ATTR_FLOOR_TEMP,
    ATTR_SETPOINT_IDLE,
    ATTR_SETPOINT_ACTIVE,
    ATTR_FAN_OPTIONS,
    ATTR_SETPOINT_OFFSET,
    MANUFACTURER,
)
from .coordinator import HiqDataUpdateCoordinator
from .models import HiqEntity
from .light import is_general_error_ok
from . import get_write_req_th

SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
)

SUPPORT_MODES_HEAT = [HVACMode.OFF, HVACMode.HEAT]
SUPPORT_MODES_COOL = [HVACMode.OFF, HVACMode.COOL]

SUPPORT_PRESET_MODES_ALL = [PRESET_COMFORT, PRESET_BOOST, PRESET_ECO]
SUPPORT_PRESET_MODES = [PRESET_COMFORT, PRESET_ECO]

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

    thermostats = find_thermostats(
        coordinator,
    )
    if thermostats is not None:
        async_add_entities(thermostats)


def find_thermostats(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqThermostat] | None:
    """Find system tags in the plc vars.
    eg: c1000.th00_ and so on.
    """
    res: list[HiqThermostat] = []

    # find thermostats (general_error)
    for key in coordinator.data.plc_info.plc_vars:
        if search(r"c\d+\.th\d+_general_error", key):
            if is_general_error_ok(coordinator, key):
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
    _attr_preset_modes = SUPPORT_PRESET_MODES
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
            identifiers={(coordinator.cybro.nad, f"{self._prefix} thermostat")},
            manufacturer=MANUFACTURER,
            name=f"{self._prefix} thermostat",
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
        coordinator.data.add_var(f"{self._prefix}_fan_limit")
        coordinator.data.add_var(f"{self._prefix}_fan_options")
        coordinator.data.add_var(f"{self._nad}.hvac_mode")

    @property
    def current_temperature(self) -> float | None:
        """Return the reported current temperature for the device."""
        return self.coordinator.get_value(f"{self._prefix}_temperature", 0.1, 1)

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        if (
            humidity := self.coordinator.get_value(f"{self._prefix}_humidity", 1.0, 0)
        ) is None:
            return None
        if humidity > 0:
            return humidity
        return None

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the hvac action."""
        mode = CYBRO_TO_HA_HVAC_MODE_MAP[
            self.coordinator.get_value(f"{self._nad}.hvac_mode", def_val=1)
        ]
        if mode == HVACMode.HEAT:
            return CYBRO_TO_HA_HVAC_ACTION_HEAT_MAP[
                self.coordinator.get_value(f"{self._prefix}_output", def_val=0)
            ]
        if mode == HVACMode.COOL:
            return CYBRO_TO_HA_HVAC_ACTION_COOL_MAP[
                self.coordinator.get_value(f"{self._prefix}_output", def_val=0)
            ]
        return HVACAction.OFF

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature for the device."""
        # update min / max to actual values from thermostat
        self._attr_min_temp = self.coordinator.get_value(
            f"{self._prefix}_setpoint_lo", 0.1, 1, 0.0
        )
        self._attr_max_temp = self.coordinator.get_value(
            f"{self._prefix}_setpoint_hi", 0.1, 1, 40.0
        )
        if sp := self.coordinator.get_value(
            f"{self._prefix}_setpoint_active", 0.1, 1, None
        ):
            return sp
        if self.preset_mode in (PRESET_BOOST, PRESET_COMFORT):
            return self.coordinator.get_value(f"{self._prefix}_setpoint", 0.1, 1)
        return self.coordinator.get_value(f"{self._prefix}_setpoint_idle", 0.1, 1)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode for the device."""
        mode = CYBRO_TO_HA_HVAC_MODE_MAP[
            self.coordinator.get_value(f"{self._nad}.hvac_mode", def_val=1)
        ]
        if mode == HVACMode.HEAT:
            self._attr_hvac_modes = SUPPORT_MODES_HEAT
            return CYBRO_TO_HA_HVAC_HEAT_MAP[
                self.coordinator.get_value(f"{self._prefix}_active", def_val=0)
            ]
        if mode == HVACMode.COOL:
            self._attr_hvac_modes = SUPPORT_MODES_COOL
            return CYBRO_TO_HA_HVAC_COOL_MAP[
                self.coordinator.get_value(f"{self._prefix}_active", def_val=0)
            ]
        self._attr_hvac_modes = list(HVACMode.OFF)
        HVACMode.OFF

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp.

        Requires ClimateEntityFeature.PRESET_MODE.
        """
        # set supported presets
        if (
            CYBRO_TO_HA_HVAC_MODE_MAP[
                self.coordinator.get_value(f"{self._nad}.hvac_mode", def_val=1)
            ]
            == HVACMode.OFF
        ):
            self._attr_preset_modes = None
        else:
            self._attr_preset_modes = SUPPORT_PRESET_MODES
            # allow boost only if fan max is enabled on thermostat
            if (
                self.coordinator.get_value(f"{self._prefix}_fan_options", 1.0, 0, 0)
                >> 4
                & 1
            ) != 0:
                self._attr_preset_modes = SUPPORT_PRESET_MODES_ALL

        if self.coordinator.get_value(f"{self._prefix}_fan_limit", 1.0, 0, 0) == 4:
            return PRESET_BOOST
        if self.coordinator.get_value(f"{self._prefix}_active", 1.0, 0, 0) == 1:
            return PRESET_COMFORT
        if self.coordinator.get_value(f"{self._prefix}_setpoint_idle", 0.1, 0, 0) > 0:
            return PRESET_ECO
        return PRESET_NONE

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        data = {}
        if (
            floor_tmp := self.coordinator.get_value(f"{self._prefix}_floor_tmp", 0.1, 1)
            or None
        ):
            data[ATTR_FLOOR_TEMP] = floor_tmp
        if (
            setp_idle := self.coordinator.get_value(
                f"{self._prefix}_setpoint_idle", 0.1, 1
            )
            or None
        ):
            data[ATTR_SETPOINT_IDLE] = setp_idle
        if (
            setp_act := self.coordinator.get_value(
                f"{self._prefix}_setpoint_active", 0.1, 1
            )
            or None
        ):
            data[ATTR_SETPOINT_ACTIVE] = setp_act
        if (
            setp_off := self.coordinator.get_value(
                f"{self._prefix}_setpoint_offset", 0.1, 1
            )
            or None
        ):
            data[ATTR_SETPOINT_OFFSET] = setp_off
        if (
            fan_opts := self.coordinator.get_value(
                f"{self._prefix}_fan_options", 1.0, 0, 0
            )
            or None
        ):
            data[ATTR_FAN_OPTIONS] = fan_opts
        return data

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode to device."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.cybro.write_var(f"{self._prefix}_active", "0")
        else:
            await self.coordinator.cybro.write_var(f"{self._prefix}_active", "1")
        await self.coordinator.async_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_BOOST:
            await self.coordinator.cybro.write_var(f"{self._prefix}_fan_limit", "4")
        elif preset_mode == PRESET_COMFORT:
            await self.coordinator.cybro.write_var(f"{self._prefix}_active", "1")
        elif preset_mode == PRESET_ECO:
            await self.coordinator.cybro.write_var(f"{self._prefix}_active", "0")
        await self.coordinator.async_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        tags = {}
        if self.preset_mode == PRESET_BOOST and self.hvac_mode == HVACMode.HEAT:
            tags[f"{self._prefix}_setpoint_hi"] = int(temperature * 10.0)
            if req := get_write_req_th(f"{self._prefix}_setpoint_hi", self._prefix):
                tags[req] = "1"
        elif self.preset_mode == PRESET_BOOST and self.hvac_mode == HVACMode.COOL:
            tags[f"{self._prefix}_setpoint_lo"] = int(temperature * 10.0)
            if req := get_write_req_th(f"{self._prefix}_setpoint_lo", self._prefix):
                tags[req] = "1"
        elif self.preset_mode == PRESET_ECO:
            tags[f"{self._prefix}_setpoint_idle"] = int(temperature * 10.0)
            if req := get_write_req_th(f"{self._prefix}_setpoint_idle", self._prefix):
                tags[req] = "1"
        else:
            tags[f"{self._prefix}_setpoint"] = int(temperature * 10.0)

        await self.coordinator.cybro.request(tags)
        await self.coordinator.async_refresh()
