"""Support for HIQ-Home button input events (socket 1, direct connection)."""

from __future__ import annotations

from re import search

from homeassistant.components.event import EventDeviceClass
from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import AREA_LIGHTS
from .const import DEVICE_DESCRIPTION
from .const import DEVICE_HW_VERSION
from .const import DEVICE_SW_VERSION
from .const import DOMAIN
from .const import INPUT_EVENT_TYPES
from .const import MANUFACTURER
from .const import MANUFACTURER_URL
from .coordinator import HiqDataUpdateCoordinator
from .light import is_general_error_ok
from .models import HiqEntity
from .models import module_device_info

# first input number and number of modules, as in read_input() of the program
INPUT_MODULES = {"lc": (0, 8), "ld": (100, 4)}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HIQ-Home button inputs based on a config entry."""
    coordinator: HiqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    # the events only come with socket 1
    if coordinator.has_socket:
        async_add_entities(find_button_inputs(coordinator))


def input_number(key: str) -> int | None:
    """Return the input number of the program, eg: c1000.ld01_ix03 -> 113."""
    match = search(r"\.(lc|ld)(\d\d)_ix(\d\d)$", key)
    if match is None:
        return None
    first, modules = INPUT_MODULES[match[1]]
    module, index = int(match[2]), int(match[3])
    if module >= modules or index > 9:
        return None
    return first + module * 10 + index


def find_button_inputs(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqButtonInput]:
    """Find the button inputs of working modules, eg: c1000.lc00_ix00."""
    return [
        HiqButtonInput(coordinator, key, number)
        for key in coordinator.data.plc_info.plc_vars
        if (number := input_number(key)) is not None
        and is_general_error_ok(coordinator, key)
    ]


def inputs_device_info(coordinator: HiqDataUpdateCoordinator, key: str) -> DeviceInfo:
    """Return the device info of the inputs of a module (eg: c1000.lc00)."""
    versions = {"model": DEVICE_DESCRIPTION, "sw_version": DEVICE_SW_VERSION}
    module = key.split("_")[0]
    return DeviceInfo(
        identifiers={(DOMAIN, f"{module} inputs")},
        manufacturer=MANUFACTURER,
        name=f"Inputs {module}",
        suggested_area=AREA_LIGHTS,
        configuration_url=MANUFACTURER_URL,
        hw_version=DEVICE_HW_VERSION,
        **(versions | module_device_info(coordinator, module)),
        **coordinator.via_device_info,
    )


class HiqButtonInput(HiqEntity, EventEntity):
    """Defines the press and release events of a button input."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_entity_registry_enabled_default = False
    _attr_event_types = INPUT_EVENT_TYPES
    _attr_has_entity_name = True
    _attr_translation_key = "button_input"

    def __init__(
        self, coordinator: HiqDataUpdateCoordinator, key: str, number: int
    ) -> None:
        """Initialize HIQ-Home button input."""
        super().__init__(coordinator=coordinator)
        self._number = number
        self._attr_unique_id = f"{key}_event"
        self._attr_translation_placeholders = {"input": key.split("_")[-1]}
        self._attr_device_info = inputs_device_info(coordinator, key)

    async def async_added_to_hass(self) -> None:
        """Receive the events of the input."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_input_listener(self._number, self._event)
        )

    @callback
    def _event(self, event_type: str) -> None:
        """Show an event of the input."""
        self._trigger_event(event_type)
        self.async_write_ha_state()
