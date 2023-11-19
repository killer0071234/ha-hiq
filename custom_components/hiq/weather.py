"""Support for the Cybro weather."""
from __future__ import annotations

from cybro import VarType
from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    AREA_WEATHER,
    ATTRIBUTION_PLC,
    DEVICE_DESCRIPTION,
    DEVICE_HW_VERSION,
    DEVICE_SW_VERSION,
    DOMAIN,
    MANUFACTURER,
    MANUFACTURER_URL,
)
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
        dev_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.cybro.nad, "weather")},
            manufacturer=MANUFACTURER,
            name=f"c{coordinator.cybro.nad} weather",
            suggested_area=AREA_WEATHER,
            model=DEVICE_DESCRIPTION,
            configuration_url=MANUFACTURER_URL,
            entry_type=None,
            sw_version=DEVICE_SW_VERSION,
            hw_version=DEVICE_HW_VERSION,
            via_device=(DOMAIN, coordinator.cybro.nad),
        )

        async_add_entities([HiqWeatherEntity(var_prefix, coordinator, dev_info)])


class HiqWeatherEntity(CoordinatorEntity, WeatherEntity):
    """Define an Weather Station entity."""

    coordinator: HiqDataUpdateCoordinator

    def __init__(
        self, var_prefix: str, coordinator: HiqDataUpdateCoordinator, device: DeviceInfo
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_name = f"c{coordinator.data.plc_info.nad} weather"
        self._attr_unique_id = var_prefix
        # setup default units from HIQ-controller
        self._attr_native_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
        self._attr_native_pressure_unit = UnitOfPressure.HPA
        self._attr_attribution = ATTRIBUTION_PLC
        self._attr_device_info = device

    @property
    def device_info(self):
        """Return the device info."""
        if self._attr_device_info is not None:
            return self._attr_device_info
        return DeviceInfo(
            identifiers={(DOMAIN, self.platform.config_entry.unique_id)},
            manufacturer=MANUFACTURER,
            configuration_url=MANUFACTURER_URL,
            name=f"c{self.coordinator.cybro.nad} weather",
            model=DEVICE_DESCRIPTION,
        )

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return ""

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return self.coordinator.get_value(f"{self._attr_unique_id}temperature", 0.1, 1)

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        return self.coordinator.get_value(f"{self._attr_unique_id}pressure")

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        return self.coordinator.get_value(f"{self._attr_unique_id}humidity")

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        return self.coordinator.get_value(f"{self._attr_unique_id}wind_speed", 0.1, 1)

    @property
    def wind_bearing(self) -> int | None:
        """Return the wind bearing."""
        return self.coordinator.get_value(f"{self._attr_unique_id}wind_direction")
