"""Support for HIQ-Home lights."""
from __future__ import annotations

import re

from typing import Any
from xmlrpc.client import Boolean

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from sqlalchemy import false

from .const import AREA_LIGHTS
from .const import ATTR_DESCRIPTION
from .const import DEVICE_DESCRIPTION
from .const import DOMAIN
from .const import LOGGER
from .const import MANUFACTURER
from .const import MANUFACTURER_URL
from .coordinator import HiqDataUpdateCoordinator
from .models import HiqEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HIQ-Home light based on a config entry."""
    coordinator: HiqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    lights = find_on_off_lights(coordinator)
    if lights is not None:
        async_add_entities(lights)


def is_general_error_ok(coordinator: HiqDataUpdateCoordinator, var: str) -> bool:
    ge_names = re.findall(r".*\_", var)
    if ge_names is None:
        return False
    ge_name = f"{ge_names[0]}general_error"
    coordinator.data.add_var(ge_name)
    ge_val = coordinator.data.vars.get(ge_name, None)
    if ge_val is None:
        return False
    LOGGER.debug("%s -> %s", ge_name, ge_val.value)
    return bool(ge_val.value == "1")


def find_on_off_lights(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqUpdateLight] | None:
    """Find simple light objects in the plc vars.
    eg: c1000.lc00_qx00 and so on
    """
    res: list[HiqUpdateLight] = []
    for key in coordinator.data.plc_info.plc_vars:
        if key.find(".lc") != -1 and key.find("_qx") != -1:
            dev_info = DeviceInfo(
                identifiers={(DOMAIN, key)},
                manufacturer=MANUFACTURER,
                default_name=f"{key} light output",
                suggested_area=AREA_LIGHTS,
                enabled=is_general_error_ok(coordinator, key),
                model=DEVICE_DESCRIPTION,
                configuration_url=MANUFACTURER_URL,
            )
            res.append(HiqUpdateLight(coordinator, key, dev_info=dev_info))

    if len(res) > 0:
        return res
    return None


class HiqUpdateLight(HiqEntity, LightEntity):
    """Defines a Simple HIQ-Home light."""

    def __init__(
        self,
        coordinator: HiqDataUpdateCoordinator,
        var_name: str = "",
        attr_icon="mdi:lightbulb",
        dev_info: DeviceInfo = None,
        enabled: Boolean = True,
    ) -> None:
        """Initialize HIQ-Home light."""
        super().__init__(coordinator=coordinator)
        if var_name == "":
            return
        self._attr_unique_id = var_name
        self._attr_name = f"Light {var_name}"
        self._attr_icon = attr_icon
        self._attr_device_info = dev_info
        self._attr_entity_registry_enabled_default = enabled
        LOGGER.debug(self._attr_unique_id)
        coordinator.data.add_var(self._attr_unique_id, var_type=0)

    @property
    def device_info(self):
        """Return the device info."""
        if self._attr_device_info is not None:
            return self._attr_device_info
        return DeviceInfo(
            identifiers={(DOMAIN, self.platform.config_entry.unique_id)},
            manufacturer=MANUFACTURER,
            configuration_url=MANUFACTURER_URL,
            name=f"c{self.coordinator.cybro.nad} light output",
            model=DEVICE_DESCRIPTION,
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the light."""
        res = self.coordinator.data.vars.get(self._attr_unique_id, None)
        if res is None:
            return false
        return bool(res.value == "1")

    @property
    def available(self) -> bool:
        """Return if this light is available or not."""
        res = self.coordinator.data.vars.get(self._attr_unique_id, None)
        if res is None:
            return false
        return res.value != "?"

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""

        await self.coordinator.cybro.write_var(self.unique_id, "0")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self.coordinator.cybro.write_var(self.unique_id, "1")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        try:
            desc = self.coordinator.data.vars[self._attr_unique_id].description
        except KeyError:
            desc = self._attr_name
        return {
            ATTR_DESCRIPTION: desc,
        }
