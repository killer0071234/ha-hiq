"""Support for HIQ-Home lights."""
from __future__ import annotations

from dataclasses import dataclass
from re import sub
from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.light import ATTR_HS_COLOR
from homeassistant.components.light import ColorMode
from homeassistant.components.light import LightEntity
from homeassistant.components.light import LightEntityDescription
from homeassistant.components.light import filter_supported_color_modes
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import AREA_LIGHTS
from .const import ATTR_DESCRIPTION
from .const import ATTR_VARIABLE
from .const import DEVICE_DESCRIPTION
from .const import DEVICE_HW_VERSION
from .const import DEVICE_SW_VERSION
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

    lights = find_on_off_lights(
        coordinator,
    )
    if lights is not None:
        async_add_entities(lights)

    lights = find_dimm_lights(coordinator)
    if lights is not None:
        async_add_entities(lights)


@dataclass
class HiqLightEntityDescription(LightEntityDescription):
    """HIQ Light Entity."""

    def __post_init__(self):
        """Defaults the translation_key to the sensor key."""
        self.has_entity_name = True
        self.translation_key = (
            self.translation_key
            or sub(r"c\d+\.", "", self.key).replace(".", "_").lower()
        )


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
            if is_general_error_ok(coordinator, key):
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
                        entity_description=HiqLightEntityDescription(
                            key=key,
                            translation_key="light",
                        ),
                        dev_info=dev_info,
                    )
                )

    if len(res) > 0:
        return res
    return None


def find_dimm_lights(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqUpdateLight] | None:
    """Find dimmable light objects in the plc vars.
    eg: c1000.ld00_qw00 and so on.
    """
    res: list[HiqUpdateLight] = []
    for key in coordinator.data.plc_info.plc_vars:
        if key.find(".ld") != -1 and key.find("_qw") != -1:
            if is_general_error_ok(coordinator, key):
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
                        entity_description=HiqLightEntityDescription(
                            key=key,
                            translation_key="light",
                        ),
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
        entity_description: HiqLightEntityDescription | None = None,
        unique_id: str | None = None,
        attr_icon="mdi:lightbulb",
        dev_info: DeviceInfo = None,
        dimming_out: str | None = None,
        rgb_hue_out: str | None = None,
        rgb_sat_out: str | None = None,
    ) -> None:
        """Initialize HIQ-Home light."""
        super().__init__(coordinator=coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = unique_id or entity_description.key
        self._dimming_out = dimming_out
        self._rgb_hue_out = rgb_hue_out
        self._rgb_sat_out = rgb_sat_out
        # self._attr_name = f"Light {var_name}"
        self._attr_icon = attr_icon
        self._attr_device_info = dev_info
        LOGGER.debug(self._attr_unique_id)
        coordinator.data.add_var(self._attr_unique_id, var_type=0)
        supported_color_modes: set[ColorMode] = set()
        if dimming_out:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            supported_color_modes.add(ColorMode.BRIGHTNESS)
            LOGGER.debug("dimming light: %s", self._attr_unique_id)
        if rgb_hue_out and rgb_sat_out:
            self._attr_color_mode = ColorMode.HS
            supported_color_modes.add(ColorMode.HS)
            LOGGER.debug("rgb light: %s", self._attr_unique_id)

        if not supported_color_modes:
            self._attr_color_mode = ColorMode.ONOFF
            supported_color_modes.add(ColorMode.ONOFF)
        # Validate the color_modes configuration
        self._attr_supported_color_modes = filter_supported_color_modes(
            supported_color_modes
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
        return self.coordinator.get_value(self._attr_unique_id, 1.0, 0, None)

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
            desc = "?"
        return {
            ATTR_DESCRIPTION: desc,
            ATTR_VARIABLE: self._attr_unique_id,
        }
