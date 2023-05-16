"""Support for HIQ-Home lights."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    AREA_LIGHTS,
    ATTR_DESCRIPTION,
    CONF_IGNORE_GENERAL_ERROR,
    DEVICE_DESCRIPTION,
    DOMAIN,
    LOGGER,
    MANUFACTURER,
    MANUFACTURER_URL,
)
from .coordinator import HiqDataUpdateCoordinator
from .models import HiqEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HIQ-Home light based on a config entry."""
    coordinator: HiqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    lights = find_on_off_lights(
        coordinator, entry.options.get(CONF_IGNORE_GENERAL_ERROR, False)
    )
    if lights is not None:
        async_add_entities(lights)

    lights = find_dimm_lights(coordinator, entry.data[CONF_IGNORE_GENERAL_ERROR])
    if lights is not None:
        async_add_entities(lights)


def is_general_error_ok(coordinator: HiqDataUpdateCoordinator, var: str) -> bool:
    """Check if general error of own module is ok."""
    ge_names = var.split("_")
    if ge_names is None:
        return False
    ge_name = f"{ge_names[0]}_general_error"
    coordinator.data.add_var(ge_name)
    ge_val = coordinator.data.vars.get(ge_name, None)
    if ge_val is None:
        return False
    return bool(ge_val.value == "0")


def find_on_off_lights(
    coordinator: HiqDataUpdateCoordinator,
    add_all: bool,
) -> list[HiqUpdateLight] | None:
    """Find simple light objects in the plc vars.
    eg: c1000.lc00_qx00 and so on.
    """
    res: list[HiqUpdateLight] = []
    for key in coordinator.data.plc_info.plc_vars:
        if (
            key.find(".lc") != -1
            and key.find("_qx") != -1
            and _is_dimm_light(key) is False
        ):
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                dev_info = DeviceInfo(
                    identifiers={(DOMAIN, key)},
                    manufacturer=MANUFACTURER,
                    default_name=f"Light {key}",
                    suggested_area=AREA_LIGHTS,
                    enabled=ge_ok,
                    model=DEVICE_DESCRIPTION,
                    configuration_url=MANUFACTURER_URL,
                )
                res.append(HiqUpdateLight(coordinator, key, dev_info=dev_info))

    if len(res) > 0:
        return res
    return None


def find_dimm_lights(
    coordinator: HiqDataUpdateCoordinator,
    add_all: bool,
) -> list[HiqUpdateLight] | None:
    """Find dimmable light objects in the plc vars.
    eg: c1000.ld00_qw00 and so on
    """
    res: list[HiqUpdateLight] = []
    for key in coordinator.data.plc_info.plc_vars:
        if key.find(".ld") != -1 and key.find("_qw") != -1:
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                is_rgb_light = _is_rgb_light(coordinator, key)
                LOGGER.debug(is_rgb_light)
                dev_info = DeviceInfo(
                    identifiers={(DOMAIN, key)},
                    manufacturer=MANUFACTURER,
                    default_name=f"Light {key}",
                    suggested_area=AREA_LIGHTS,
                    enabled=ge_ok,
                    model=DEVICE_DESCRIPTION,
                    configuration_url=MANUFACTURER_URL,
                )
                res.append(HiqUpdateLight(coordinator, key, dev_info=dev_info))

    if len(res) > 0:
        return res
    return None


def _is_dimm_light(var: str) -> bool:
    """Helper to check if there exists a dimming light of it."""
    return var.find("qw") != -1


def _is_rgb_light(coordinator: HiqDataUpdateCoordinator, var: str) -> bool:
    var_names = var.split("_")
    if var_names is None:
        return False
    if var_names[1] in ("qw00", "qw01", "qw02", "qw03"):
        rgb_mode_var = f"{var_names[0]}_rgb_mode"
        # white_mode_var = f"{var_names[0]}_white_channel"
    elif var_names[1] in ("qw04", "qw05", "qw06", "qw07"):
        rgb_mode_var = f"{var_names[0]}_rgb_mode_2"
        # white_mode_var = f"{var_names[0]}_white_channel_2"
    else:
        return False
    coordinator.data.add_var(rgb_mode_var)
    # coordinator.data.add_var(white_mode_var)
    rgb_val = coordinator.data.vars.get(rgb_mode_var, None)
    # white_val = coordinator.data.vars.get(white_mode_var, None)
    if rgb_val is None:
        return False
    LOGGER.debug(
        "%s -> %s",
        rgb_mode_var,
        rgb_val.value,
    )
    return bool(rgb_val.value == "1")


class HiqUpdateLight(HiqEntity, LightEntity):
    """Defines a Simple HIQ-Home light."""

    def __init__(
        self,
        coordinator: HiqDataUpdateCoordinator,
        var_name: str = "",
        attr_icon="mdi:lightbulb",
        dev_info: DeviceInfo = None,
        enabled: bool = True,
        dimming_out: str | None = None,
    ) -> None:
        """Initialize HIQ-Home light."""
        super().__init__(coordinator=coordinator)
        if var_name == "":
            return
        self._attr_unique_id = var_name
        self._dimming_out = dimming_out
        self._attr_name = f"Light {var_name}"
        self._attr_icon = attr_icon
        self._attr_device_info = dev_info
        if enabled is False:
            self._attr_entity_registry_enabled_default = False
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
    def brightness(self) -> int | None:
        """Return the brightness of this light between 1..255."""
        if self._dimming_out is None:
            return None
        res = self.coordinator.data.vars.get(self._dimming_out, None)
        if res is None or res.value == "?":
            LOGGER.debug("%s -> unknown brightness", self._attr_unique_id)
            return None
        return int(int(res.value) * 2.55)

    @property
    def is_on(self) -> bool:
        """Return the state of the light."""
        res = self.coordinator.data.vars.get(self._attr_unique_id, None)
        if res is None or res.value != "1":
            return False
        return True

    @property
    def available(self) -> bool:
        """Return if this light is available or not."""
        res = self.coordinator.data.vars.get(self._attr_unique_id, None)
        if res is None or res.value == "?":
            LOGGER.debug("%s -> not available", self._attr_unique_id)
            return False
        return True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self.coordinator.cybro.write_var(self.unique_id, "0")
        await self.coordinator.async_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self.coordinator.cybro.write_var(self.unique_id, "1")
        await self.coordinator.async_refresh()

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
