"""Support for the Cybro weather."""
from __future__ import annotations

from typing import cast

from cybro import VarType
from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UNIT_SYSTEM_METRIC
from homeassistant.const import SPEED_KILOMETERS_PER_HOUR
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from sqlalchemy import false
from sqlalchemy import true

from .const import AREA_WEATHER
from .const import ATTRIBUTION_PLC
from .const import DEVICE_DESCRIPTION
from .const import DOMAIN
from .const import MANUFACTURER
from .const import MANUFACTURER_URL
from .coordinator import HiqDataUpdateCoordinator

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a User Programmed Weather Station entity from a config_entry."""

    coordinator: HiqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    var_prefix = f"c{coordinator.data.plc_info.nad}.weather_"
    has_weather: bool = false
    # search for any weather station var and add it into the read list
    if coordinator.data.plc_info.plc_vars.__contains__(f"{var_prefix}temperature"):
        coordinator.data.add_var(f"{var_prefix}temperature", var_type=VarType.INT)
        has_weather = true
    if coordinator.data.plc_info.plc_vars.__contains__(f"{var_prefix}humidity"):
        coordinator.data.add_var(f"{var_prefix}humidity", var_type=VarType.INT)
        has_weather = true
    if coordinator.data.plc_info.plc_vars.__contains__(f"{var_prefix}wind_speed"):
        coordinator.data.add_var(f"{var_prefix}wind_speed", var_type=VarType.INT)
        has_weather = true
    if coordinator.data.plc_info.plc_vars.__contains__(f"{var_prefix}wind_direction"):
        coordinator.data.add_var(f"{var_prefix}wind_direction", var_type=VarType.INT)
        has_weather = true
    if coordinator.data.plc_info.plc_vars.__contains__(f"{var_prefix}pressure"):
        coordinator.data.add_var(f"{var_prefix}pressure", var_type=VarType.INT)
        has_weather = true

    if has_weather is True:
        async_add_entities([HiqWeatherEntity(var_prefix, coordinator)])


class HiqWeatherEntity(CoordinatorEntity, WeatherEntity):
    """Define an Weather Station entity."""

    coordinator: HiqDataUpdateCoordinator

    def __init__(self, var_prefix: str, coordinator: HiqDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._unit_system = CONF_UNIT_SYSTEM_METRIC
        self._attr_name = (
            f"User Weather Station connected to c{coordinator.data.plc_info.nad}"
        )
        self._attr_unique_id = var_prefix
        self._attr_temperature_unit = TEMP_CELSIUS
        self._attr_attribution = ATTRIBUTION_PLC
        self._attr_pressure_unit = SPEED_KILOMETERS_PER_HOUR
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, var_prefix)},
            manufacturer=MANUFACTURER,
            default_name="HIQ-Home weather station",
            suggested_area=AREA_WEATHER,
            model=DEVICE_DESCRIPTION,
        )

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
    def condition(self) -> str | None:
        """Return the current condition."""
        return ""

    @property
    def temperature(self) -> float | None:
        """Return the temperature."""
        try:
            return cast(
                float,
                self.coordinator.data.vars[
                    f"{self._attr_unique_id}temperature"
                ].value_float()
                * 0.1,
            )
        except KeyError:
            return None

    @property
    def pressure(self) -> float | None:
        """Return the pressure."""
        try:
            return cast(
                float,
                self.coordinator.data.vars[
                    f"{self._attr_unique_id}pressure"
                ].value_float(),
            )
        except KeyError:
            return None

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        try:
            return cast(
                float,
                self.coordinator.data.vars[
                    f"{self._attr_unique_id}humidity"
                ].value_float(),
            )
        except KeyError:
            return None

    @property
    def wind_speed(self) -> float | None:
        """Return the wind speed."""
        try:
            return cast(
                float,
                self.coordinator.data.vars[
                    f"{self._attr_unique_id}wind_speed"
                ].value_float()
                * 0.1,
            )
        except KeyError:
            return None

    @property
    def wind_bearing(self) -> int | None:
        """Return the wind bearing."""
        try:
            return self.coordinator.data.vars[
                f"{self._attr_unique_id}wind_direction"
            ].value_int()
        except KeyError:
            return None
