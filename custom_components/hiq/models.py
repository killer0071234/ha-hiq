"""Models for HIQ-Home."""

from homeassistant.const import (
    ATTR_CONFIGURATION_URL,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    AREA_CLIMATE,
    DEVICE_DESCRIPTION,
    MANUFACTURER,
    MANUFACTURER_URL,
)
from .coordinator import HiqDataUpdateCoordinator


def thermostat_device_info(
    coordinator: HiqDataUpdateCoordinator, th_prefix: str
) -> DeviceInfo:
    """Return the device info of a thermostat, eg: c1000.th00."""
    return DeviceInfo(
        identifiers={(coordinator.cybro.nad, f"{th_prefix} thermostat")},
        manufacturer=MANUFACTURER,
        name=f"{th_prefix} thermostat",
        suggested_area=AREA_CLIMATE,
        **coordinator.via_device_info,
    )


def hvac_device_info(coordinator: HiqDataUpdateCoordinator, prefix: str) -> DeviceInfo:
    """Return the device info of the global hvac settings, eg: c1000."""
    return DeviceInfo(
        identifiers={(coordinator.cybro.nad, f"{prefix} HVAC")},
        manufacturer=MANUFACTURER,
        name=f"{prefix} HVAC",
        suggested_area=AREA_CLIMATE,
        **coordinator.via_device_info,
    )


class HiqEntity(CoordinatorEntity):
    """Defines a base HIQ entity."""

    coordinator: HiqDataUpdateCoordinator

    @property
    def device_info(self):
        """Return device information about this HIQ controller."""
        if self._attr_device_info:
            return self._attr_device_info
        return {
            ATTR_IDENTIFIERS: {
                # Serial numbers are unique identifiers within a specific domain
                (self.coordinator.cybro.nad, self.name)
            },
            ATTR_NAME: self.name,
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: DEVICE_DESCRIPTION,
            ATTR_SW_VERSION: self.coordinator.data.server_info.server_version,
            ATTR_CONFIGURATION_URL: MANUFACTURER_URL,
        }
