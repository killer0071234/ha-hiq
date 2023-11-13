"""Support for HIQ-Home lights."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    LightEntity,
    ColorMode,
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
)
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
    DEVICE_HW_VERSION,
    DEVICE_SW_VERSION,
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

    ignore_general_error = entry.options.get(CONF_IGNORE_GENERAL_ERROR, False)

    lights = find_on_off_lights(
        coordinator,
        ignore_general_error,
    )
    if lights is not None:
        async_add_entities(lights)

    lights = find_dimm_lights(coordinator, ignore_general_error)
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
                    name=f"Light {key}",
                    suggested_area=AREA_LIGHTS,
                    model=DEVICE_DESCRIPTION,
                    configuration_url=MANUFACTURER_URL,
                    entry_type=None,
                    sw_version=DEVICE_SW_VERSION,
                    hw_version=DEVICE_HW_VERSION,
                    via_device=(DOMAIN, coordinator.cybro.nad),
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
    eg: c1000.ld00_qw00 and so on.
    """
    res: list[HiqUpdateLight] = []
    for key in coordinator.data.plc_info.plc_vars:
        if key.find(".ld") != -1 and key.find("_qw") != -1:
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                is_rgb_light = _is_rgb_light(coordinator, key)
                rgb_hue_out = None
                rgb_sat_out = None
                LOGGER.debug("%s is rgb light? -> %s", key, is_rgb_light)
                if is_rgb_light:
                    var_names = key.split("_")
                    if var_names[1] in ("qw00"):
                        rgb_hue_out = var_names[0] + "_qw01"
                        rgb_sat_out = var_names[0] + "_qw02"
                    elif var_names[1] in ("qw04"):
                        rgb_hue_out = var_names[0] + "_qw05"
                        rgb_sat_out = var_names[0] + "_qw06"
                    elif var_names[1] in (
                        "qw01",
                        "qw02",
                        "qw03",
                        "qw05",
                        "qw06",
                        "qw07",
                    ):
                        continue
                LOGGER.debug(
                    "%s: rgb_hue_out -> %s, rgb_sat_out -> %s",
                    key,
                    rgb_hue_out,
                    rgb_sat_out,
                )
                dev_info = DeviceInfo(
                    identifiers={(DOMAIN, key)},
                    manufacturer=MANUFACTURER,
                    name=f"Light {key}",
                    suggested_area=AREA_LIGHTS,
                    model=DEVICE_DESCRIPTION,
                    configuration_url=MANUFACTURER_URL,
                    entry_type=None,
                    sw_version=DEVICE_SW_VERSION,
                    hw_version=DEVICE_HW_VERSION,
                    via_device=(DOMAIN, coordinator.cybro.nad),
                )
                res.append(
                    HiqUpdateLight(
                        coordinator,
                        key,
                        dev_info=dev_info,
                        dimming_out=key,
                        rgb_hue_out=rgb_hue_out,
                        rgb_sat_out=rgb_sat_out,
                    )
                )

    if len(res) > 0:
        return res
    return None


def _is_dimm_light(var: str) -> bool:
    """Check if tag is a dimmer output."""
    return var.find("_qw") != -1


def _is_rgb_light(coordinator: HiqDataUpdateCoordinator, var: str) -> bool:
    """Check if we had a rgb light."""
    var_names = var.split("_")
    if var_names is None:
        return False
    if var_names[1] in ("qw00", "qw01", "qw02", "qw03"):
        rgb_mode_var = f"{var_names[0]}_rgb_mode"
    elif var_names[1] in ("qw04", "qw05", "qw06", "qw07"):
        rgb_mode_var = f"{var_names[0]}_rgb_mode_2"
    else:
        return False

    coordinator.data.add_var(rgb_mode_var)
    rgb_val = coordinator.data.vars.get(rgb_mode_var, None)
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
        rgb_hue_out: str | None = None,
        rgb_sat_out: str | None = None,
    ) -> None:
        """Initialize HIQ-Home light."""
        super().__init__(coordinator=coordinator)
        if var_name == "":
            return
        self._attr_unique_id = var_name
        self._dimming_out = dimming_out
        self._rgb_hue_out = rgb_hue_out
        self._rgb_sat_out = rgb_sat_out
        self._attr_name = f"Light {var_name}"
        self._attr_icon = attr_icon
        self._attr_device_info = dev_info
        if enabled is False:
            self._attr_entity_registry_enabled_default = False
        LOGGER.debug(self._attr_unique_id)
        coordinator.data.add_var(self._attr_unique_id, var_type=0)
        if dimming_out:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            LOGGER.debug("dimming light: %s", var_name)
        if rgb_hue_out and rgb_sat_out:
            self._attr_color_mode = ColorMode.HS
            self._attr_supported_color_modes = {ColorMode.HS}
            LOGGER.debug("rgb light: %s", var_name)

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
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        if self._rgb_hue_out is None or self._rgb_sat_out is None:
            return None
        hue = self.coordinator.data.vars.get(self._rgb_hue_out, None)
        sat = self.coordinator.data.vars.get(self._rgb_sat_out, None)
        if sat is None or sat.value == "?" or hue is None or hue.value == "?":
            return None
        return [int(int(hue.value) * 3.6), int(sat.value)]

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
        if res is None or res.value == "0" or res.value == "?":
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
        LOGGER.debug("Light '%s' -> %s", self._attr_unique_id, kwargs)
        if ATTR_BRIGHTNESS in kwargs:
            await self.coordinator.cybro.write_var(
                self._dimming_out, str(int(kwargs[ATTR_BRIGHTNESS]) / 2.55)
            )
        if ATTR_HS_COLOR in kwargs:
            hue, sat = kwargs[ATTR_HS_COLOR]
            await self.coordinator.cybro.write_var(
                self._rgb_hue_out, str(int(int(hue) / 3.6))
            )
            await self.coordinator.cybro.write_var(self._rgb_sat_out, str(int(sat)))
        if not kwargs:
            if self._dimming_out is None:
                await self.coordinator.cybro.write_var(self.unique_id, "1")
            else:
                await self.coordinator.cybro.write_var(self._dimming_out, "100")
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
