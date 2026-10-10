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
    DEVICE_HW_VERSION,
    DEVICE_SW_VERSION,
    DEVICE_UNKNOWN,
    DOMAIN,
    IEX_CARD_MODELS,
    MANUFACTURER,
    MANUFACTURER_URL,
)
from .coordinator import HiqDataUpdateCoordinator


def _module_value(coordinator: HiqDataUpdateCoordinator, var: str) -> int | None:
    """Return a positive integer value of a module variable, None if missing."""
    res = coordinator.data.vars.get(var)
    if res is None:
        return None
    try:
        value = int(res.value)
    except ValueError:  # eg: "?" if not readable
        return None
    return value if value > 0 else None


def module_device_info(
    coordinator: HiqDataUpdateCoordinator, module: str
) -> dict[str, str]:
    """Return model and sw_version of an expansion module (eg: c1000.lc00).

    Empty if the module reports neither card id nor firmware (eg: older
    controllers), so the default device info is kept.
    """
    card_id = _module_value(coordinator, f"{module}_iex_card_id")
    firmware = _module_value(coordinator, f"{module}_firmware_version")
    if card_id is None and firmware is None:
        return {}
    model = DEVICE_UNKNOWN
    if card_id is not None:
        model = IEX_CARD_MODELS.get(card_id, f"card {card_id}")
    sw_version = DEVICE_UNKNOWN
    if firmware is not None:
        # last three digits: minor, build, release, the rest is the major version
        sw_version = (
            f"{firmware // 1000}.{firmware // 100 % 10}"
            f".{firmware // 10 % 10}.{firmware % 10}"
        )
    return {"model": model, "sw_version": sw_version}


def thermostat_device_info(
    coordinator: HiqDataUpdateCoordinator, th_prefix: str
) -> DeviceInfo:
    """Return the device info of a thermostat, eg: c1000.th00."""
    versions = {"model": DEVICE_DESCRIPTION, "sw_version": DEVICE_SW_VERSION}
    return DeviceInfo(
        identifiers={(coordinator.cybro.nad, f"{th_prefix} thermostat")},
        manufacturer=MANUFACTURER,
        name=f"{th_prefix} thermostat",
        suggested_area=AREA_CLIMATE,
        configuration_url=MANUFACTURER_URL,
        hw_version=DEVICE_HW_VERSION,
        **(versions | module_device_info(coordinator, th_prefix)),
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


def custom_device_info(coordinator: HiqDataUpdateCoordinator) -> DeviceInfo:
    """Return the device info of the user defined entities, eg: c1000 custom."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{coordinator.data.plc_info.nad} custom")},
        manufacturer=MANUFACTURER,
        name=f"c{coordinator.cybro.nad} custom",
        model=DEVICE_DESCRIPTION,
        configuration_url=MANUFACTURER_URL,
        entry_type=None,
        sw_version=DEVICE_SW_VERSION,
        hw_version=DEVICE_HW_VERSION,
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
