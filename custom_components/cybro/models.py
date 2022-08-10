"""Models for HIQ-Home."""
from homeassistant.const import ATTR_CONFIGURATION_URL
from homeassistant.const import ATTR_IDENTIFIERS
from homeassistant.const import ATTR_MANUFACTURER
from homeassistant.const import ATTR_MODEL
from homeassistant.const import ATTR_NAME
from homeassistant.const import ATTR_SW_VERSION
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_DESCRIPTION
from .const import MANUFACTURER
from .const import MANUFACTURER_URL
from .coordinator import HiqDataUpdateCoordinator


class HiqEntity(CoordinatorEntity):
    """Defines a base HIQ entity."""

    coordinator: HiqDataUpdateCoordinator

    @property
    def device_info(self):
        """Return device information about this HIQ controller."""
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
