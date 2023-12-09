"""Models for HIQ-Home."""
from homeassistant.const import (
    ATTR_CONFIGURATION_URL,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_DESCRIPTION,
    MANUFACTURER,
    MANUFACTURER_URL,
)
from .coordinator import HiqDataUpdateCoordinator


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
