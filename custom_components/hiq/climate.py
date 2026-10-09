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

SUPPORT_PRESET_MODES_ALL = [PRESET_COMFORT, PRESET_BOOST, PRESET_ECO]
SUPPORT_PRESET_MODES = [PRESET_COMFORT, PRESET_ECO]

# active selects the setpoint: comfort (setpoint + offset) or eco (setpoint idle)
CYBRO_TO_HA_PRESET_MAP = {
    0: PRESET_ECO,
    1: PRESET_COMFORT,
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
    0: HVACAction.IDLE,
    1: HVACAction.COOLING,
}
CYBRO_TO_HA_HVAC_ACTION_HEAT_MAP = {
    0: HVACAction.IDLE,
    1: HVACAction.HEATING,
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
        # identifier is cNAD.thNR
        if (match := search(r"(c\d+\.th\d+)_general_error$", key)) and (
            is_general_error_ok(coordinator, key)
        ):
            res.append(HiqThermostat(coordinator, match.group(1)))

    if len(res) > 0:
        return res
    return None


class HiqThermostat(HiqEntity, ClimateEntity):
    """Representation a Hiq thermostat."""

    _attr_supported_features = SUPPORT_FLAGS
    _attr_target_temperature_step = PRECISION_TENTHS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _enable_turn_on_off_backwards_compatibility = False

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
            **coordinator.via_device_info,
        )
        self._attr_name = f"{self._prefix} thermostat"
        self._attr_unique_id = f"{self._prefix}_thermostat"

        # add tags for thermostat to coordinator
        for suffix in (
            "active",
            "output",
            "setpoint_lo",
            "setpoint_hi",
            "temperature",
            "floor_tmp",
            "humidity",
            "setpoint",
            "setpoint_idle",
            "setpoint_offset",
            "setpoint_active",
            "fan_limit",
            "fan_options",
        ):
            coordinator.data.add_var(f"{self._prefix}_{suffix}")
        coordinator.data.add_var(f"{self._nad}.hvac_mode")

    @property
    def _controller_hvac_mode(self) -> HVACMode | None:
        """Return the hvac mode of the controller, None if it is unexpected."""
        return CYBRO_TO_HA_HVAC_MODE_MAP.get(
            self.coordinator.get_value(f"{self._nad}.hvac_mode", def_val=1)
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the reported current temperature for the device."""
        return self.coordinator.get_value(f"{self._prefix}_temperature", 0.1, 1)

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        humidity = self.coordinator.get_value(f"{self._prefix}_humidity", 1.0, 0)
        if humidity is not None and humidity > 0:
            return humidity
        return None

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the hvac action."""
        mode = self._controller_hvac_mode
        output = self.coordinator.get_value(f"{self._prefix}_output", def_val=0)
        if mode == HVACMode.HEAT:
            return CYBRO_TO_HA_HVAC_ACTION_HEAT_MAP.get(output)
        if mode == HVACMode.COOL:
            return CYBRO_TO_HA_HVAC_ACTION_COOL_MAP.get(output)
        if mode == HVACMode.OFF:
            return HVACAction.OFF
        return None

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
        """Return the current HVAC mode for the device.

        Heating / cooling / off is set for all thermostats by the controller,
        so a thermostat can only be set to the mode it currently has.
        """
        return self._controller_hvac_mode

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the hvac modes, only the current one (set by the controller)."""
        return [self._controller_hvac_mode or HVACMode.OFF]

    @property
    def preset_modes(self) -> list[str] | None:
        """Return the presets, only while the controller is heating or cooling."""
        if self._controller_hvac_mode not in (HVACMode.HEAT, HVACMode.COOL):
            return None
        # allow boost only if fan max is enabled on thermostat
        fan_options = self.coordinator.get_value(
            f"{self._prefix}_fan_options", 1.0, 0, 0
        )
        if fan_options >> 4 & 1:
            return SUPPORT_PRESET_MODES_ALL
        return SUPPORT_PRESET_MODES

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp.

        Requires ClimateEntityFeature.PRESET_MODE.
        """
        if self.preset_modes is None:
            return None
        if self.coordinator.get_value(f"{self._prefix}_fan_limit", 1.0, 0, 0) == 4:
            return PRESET_BOOST
        return CYBRO_TO_HA_PRESET_MAP.get(
            self.coordinator.get_value(f"{self._prefix}_active", def_val=0)
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        data = {}
        # attributes with a zero / missing value are left out
        for attr, suffix, factor, precision in (
            (ATTR_FLOOR_TEMP, "floor_tmp", 0.1, 1),
            (ATTR_SETPOINT_IDLE, "setpoint_idle", 0.1, 1),
            (ATTR_SETPOINT_ACTIVE, "setpoint_active", 0.1, 1),
            (ATTR_SETPOINT_OFFSET, "setpoint_offset", 0.1, 1),
            (ATTR_FAN_OPTIONS, "fan_options", 1.0, 0),
        ):
            if value := self.coordinator.get_value(
                f"{self._prefix}_{suffix}", factor, precision
            ):
                data[attr] = value
        return data

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode, only the current mode is offered (see hvac_mode)."""

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

        if self.preset_mode == PRESET_BOOST and self.hvac_mode == HVACMode.HEAT:
            setpoint = f"{self._prefix}_setpoint_hi"
        elif self.preset_mode == PRESET_BOOST and self.hvac_mode == HVACMode.COOL:
            setpoint = f"{self._prefix}_setpoint_lo"
        elif self.preset_mode == PRESET_ECO:
            setpoint = f"{self._prefix}_setpoint_idle"
        else:
            setpoint = f"{self._prefix}_setpoint"

        tags: dict[str, int | str] = {setpoint: int(temperature * 10.0)}
        if req := get_write_req_th(setpoint, self._prefix):
            tags[req] = "1"
        await self.coordinator.cybro.request(tags)
        await self.coordinator.async_refresh()
