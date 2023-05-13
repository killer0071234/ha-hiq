"""Support for the Cybro weather."""
from __future__ import annotations

from typing import cast

from cybro import VarType
from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPressure, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (AREA_WEATHER, ATTRIBUTION_PLC, DEVICE_DESCRIPTION, DOMAIN,
                    MANUFACTURER, MANUFACTURER_URL)
from .coordinator import HiqDataUpdateCoordinator

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a User Programmed Weather Station entity from a config_entry."""

    coordinator: HiqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    var_prefix = f"c{coordinator.data.plc_info.nad}.weather_"
    has_weather: bool = False
    # search for any weather station var and add it into the read list
    if coordinator.data.plc_info.plc_vars.__contains__(f"{var_prefix}temperature"):
        coordinator.data.add_var(f"{var_prefix}temperature", var_type=VarType.INT)
        has_weather = True
    if coordinator.data.plc_info.plc_vars.__contains__(f"{var_prefix}humidity"):
        coordinator.data.add_var(f"{var_prefix}humidity", var_type=VarType.INT)
        has_weather = True
    if coordinator.data.plc_info.plc_vars.__contains__(f"{var_prefix}wind_speed"):
        coordinator.data.add_var(f"{var_prefix}wind_speed", var_type=VarType.INT)
        has_weather = True
    if coordinator.data.plc_info.plc_vars.__contains__(f"{var_prefix}wind_direction"):
        coordinator.data.add_var(f"{var_prefix}wind_direction", var_type=VarType.INT)
        has_weather = True
    if coordinator.data.plc_info.plc_vars.__contains__(f"{var_prefix}pressure"):
        coordinator.data.add_var(f"{var_prefix}pressure", var_type=VarType.INT)
        has_weather = True

    if has_weather is True:
        async_add_entities([HiqWeatherEntity(var_prefix, coordinator)])


class HiqWeatherEntity(CoordinatorEntity, WeatherEntity):
    """Define an Weather Station entity."""

    coordinator: HiqDataUpdateCoordinator

    def __init__(self, var_prefix: str, coordinator: HiqDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_name = f"c{coordinator.data.plc_info.nad} weather"
        self._attr_unique_id = var_prefix
        # setup default units from HIQ-controller
        self._attr_native_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
        self._attr_native_pressure_unit = UnitOfPressure.HPA
        self._attr_attribution = ATTRIBUTION_PLC
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, var_prefix)},
            manufacturer=MANUFACTURER,
            default_name=f"c{coordinator.data.plc_info.nad} weather",
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
            name=f"Weather c{self.coordinator.cybro.nad}",
            model=DEVICE_DESCRIPTION,
        )

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return ""

    @property
    def native_temperature(self) -> float | None:
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
    def native_pressure(self) -> float | None:
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
    def native_wind_speed(self) -> float | None:
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
