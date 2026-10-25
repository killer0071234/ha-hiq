"""Support for HIQ-Home lights."""

from __future__ import annotations

from dataclasses import dataclass
from re import sub
from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.light import ATTR_COLOR_TEMP_KELVIN
from homeassistant.components.light import ATTR_HS_COLOR
from homeassistant.components.light import ColorMode
from homeassistant.components.light import LightEntity
from homeassistant.components.light import LightEntityDescription
from homeassistant.components.light import filter_supported_color_modes
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData
from homeassistant.helpers.restore_state import RestoredExtraData
from homeassistant.helpers.restore_state import RestoreEntity

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
from .models import module_device_info


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
    # read during setup, before the platforms
    ge_name = f"{var.split('_')[0]}_general_error"
    ge_val = coordinator.data.vars.get(ge_name)
    if ge_val is None:
        return False
    return ge_val.value == "0"


def find_on_off_lights(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqUpdateLight] | None:
    """Find simple light objects in the plc vars.
    eg: c1000.lc00_qx00 and so on.
    """
    res: list[HiqUpdateLight] = []
    for key in coordinator.data.plc_info.plc_vars:
        if not (
            ".lc" in key
            and "_qx" in key
            and not _is_dimm_light(key)
            and is_general_error_ok(coordinator, key)
        ):
            continue
        res.append(
            HiqUpdateLight(
                coordinator,
                entity_description=HiqLightEntityDescription(
                    key=key,
                    translation_key="light",
                ),
                dev_info=light_device_info(coordinator, key),
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
        if not (
            ".ld" in key and "_qw" in key and is_general_error_ok(coordinator, key)
        ):
            continue
        module, output = key.split("_")[:2]
        if f"{module}_rgb_index" in coordinator.data.plc_info.plc_vars:
            # LD-D10: every output is a light with its own color mode
            res.append(
                HiqColorChannelLight(
                    coordinator,
                    entity_description=HiqLightEntityDescription(
                        key=key,
                        translation_key="light",
                    ),
                    dev_info=light_device_info(coordinator, key),
                    dimming_out=key,
                    module=module,
                    channel=int(output.removeprefix("qw")),
                )
            )
            continue
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
            elif var_names[1] in ("qw01", "qw02", "qw03", "qw05", "qw06", "qw07"):
                # hue / saturation channels are part of the rgb light
                continue
        LOGGER.debug(
            "%s: rgb_hue_out -> %s, rgb_sat_out -> %s", key, rgb_hue_out, rgb_sat_out
        )
        res.append(
            HiqUpdateLight(
                coordinator,
                entity_description=HiqLightEntityDescription(
                    key=key,
                    translation_key="light",
                ),
                dev_info=light_device_info(coordinator, key),
                dimming_out=key,
                rgb_hue_out=rgb_hue_out,
                rgb_sat_out=rgb_sat_out,
            )
        )

    if len(res) > 0:
        return res
    return None


def light_device_info(coordinator: HiqDataUpdateCoordinator, key: str) -> DeviceInfo:
    """Return the device info of a light output (eg: c1000.lc00_qx00)."""
    versions = {"model": DEVICE_DESCRIPTION, "sw_version": DEVICE_SW_VERSION}
    module = key.split("_")[0]
    return DeviceInfo(
        identifiers={(DOMAIN, key)},
        manufacturer=MANUFACTURER,
        name=f"Light {key}",
        suggested_area=AREA_LIGHTS,
        configuration_url=MANUFACTURER_URL,
        entry_type=None,
        hw_version=DEVICE_HW_VERSION,
        **(versions | module_device_info(coordinator, module)),
        **coordinator.via_device_info,
    )


def _is_dimm_light(var: str) -> bool:
    """Check if tag is a dimmer output."""
    return "_qw" in var


def _is_rgb_light(coordinator: HiqDataUpdateCoordinator, var: str) -> bool:
    """Check if we had a rgb light."""
    var_names = var.split("_")
    if var_names[1] in ("qw00", "qw01", "qw02", "qw03"):
        rgb_mode_var = f"{var_names[0]}_rgb_mode"
    elif var_names[1] in ("qw04", "qw05", "qw06", "qw07"):
        rgb_mode_var = f"{var_names[0]}_rgb_mode_2"
    else:
        return False

    # read during setup, before the platforms (missing if the module has none)
    rgb_val = coordinator.data.vars.get(rgb_mode_var)
    if rgb_val is None:
        return False
    LOGGER.debug(
        "%s -> %s",
        rgb_mode_var,
        rgb_val.value,
    )
    return rgb_val.value == "1"


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
        self._attr_icon = attr_icon
        self._attr_device_info = dev_info
        LOGGER.debug(self._attr_unique_id)
        self.poll_var(self._attr_unique_id)
        for var in (rgb_hue_out, rgb_sat_out):
            if var:
                self.poll_var(var)
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
        hue = self.coordinator.data.vars.get(self._rgb_hue_out)
        sat = self.coordinator.data.vars.get(self._rgb_sat_out)
        if sat is None or sat.value == "?" or hue is None or hue.value == "?":
            return None
        return [int(int(hue.value) * 3.6), int(sat.value)]

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 1..255."""
        if self._dimming_out is None:
            return None
        res = self.coordinator.data.vars.get(self._dimming_out)
        if res is None or res.value == "?":
            LOGGER.debug("%s -> unknown brightness", self._attr_unique_id)
            return None
        # integer math, rounding half up: 50 % is 128 (not 127.4999...)
        return (int(res.value) * 255 + 50) // 100

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
                self._dimming_out,
                str(max(1, (int(kwargs[ATTR_BRIGHTNESS]) * 100 + 127) // 255)),
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


# white temperature 0..100 % on the controller, warm to cold
COLOR_TEMP_MIN_KELVIN = 2700
COLOR_TEMP_MAX_KELVIN = 6500


class HiqColorChannelLight(HiqUpdateLight, RestoreEntity):
    """Defines a dimmer output of a module with shared color registers (LD-D10).

    The color of an output is written by selecting it with rgb_index, so it can
    not be polled: the last written color is kept and restored after a restart.
    """

    _attr_min_color_temp_kelvin = COLOR_TEMP_MIN_KELVIN
    _attr_max_color_temp_kelvin = COLOR_TEMP_MAX_KELVIN

    def __init__(
        self,
        coordinator: HiqDataUpdateCoordinator,
        entity_description: HiqLightEntityDescription,
        dev_info: DeviceInfo,
        dimming_out: str,
        module: str,
        channel: int,
    ) -> None:
        """Initialize a color channel, eg: c1000.ld00 channel 3."""
        super().__init__(
            coordinator,
            entity_description=entity_description,
            dev_info=dev_info,
            dimming_out=dimming_out,
        )
        self._module = module
        self._channel = channel
        self._hs: tuple[float, float] | None = None
        self._kelvin: int | None = None
        # read during setup, before the platforms (0 standard, 1 rgb, 2 white)
        res = coordinator.data.vars.get(f"{module}_color_mode_{channel:02d}")
        color_mode = res.value if res is not None else "0"
        LOGGER.debug("%s color mode -> %s", self._attr_unique_id, color_mode)
        if color_mode == "1":
            self._attr_color_mode = ColorMode.HS
        elif color_mode == "2":
            self._attr_color_mode = ColorMode.COLOR_TEMP
        self._attr_supported_color_modes = {self._attr_color_mode}

    async def async_added_to_hass(self) -> None:
        """Restore the last written color."""
        await super().async_added_to_hass()
        if (data := await self.async_get_last_extra_data()) is None:
            return
        color = data.as_dict()
        if hs := color.get("hs_color"):
            self._hs = tuple(hs)
        self._kelvin = color.get("color_temp_kelvin")

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Return the color to restore, also kept while the light is off."""
        return RestoredExtraData(
            {"hs_color": self._hs, "color_temp_kelvin": self._kelvin}
        )

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the last written hue and saturation."""
        return self._hs if self._attr_color_mode == ColorMode.HS else None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the last written white temperature."""
        if self._attr_color_mode == ColorMode.COLOR_TEMP:
            return self._kelvin
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light, writing the color through the shared registers."""
        hs_color = kwargs.pop(ATTR_HS_COLOR, None)
        kelvin = kwargs.pop(ATTR_COLOR_TEMP_KELVIN, None)
        if hs_color is None and kelvin is None:
            await super().async_turn_on(**kwargs)
            return
        tags = {f"{self._module}_rgb_index": str(self._channel)}
        if hs_color is not None:
            hue, sat = hs_color
            tags[f"{self._module}_rgb_hue"] = str(int(int(hue) / 3.6))
            tags[f"{self._module}_rgb_saturation"] = str(int(sat))
        else:
            span = COLOR_TEMP_MAX_KELVIN - COLOR_TEMP_MIN_KELVIN
            percent = (int(kelvin) - COLOR_TEMP_MIN_KELVIN) * 100 / span
            tags[f"{self._module}_rgb_hue"] = str(round(min(100, max(0, percent))))
        tags[f"{self._module}_rgb_req"] = "1"
        LOGGER.debug("Light '%s' color -> %s", self._attr_unique_id, tags)
        await self.coordinator.cybro.request(tags)
        if hs_color is not None:
            self._hs = (float(hs_color[0]), float(hs_color[1]))
        else:
            self._kelvin = int(kelvin)
        if kwargs:
            await super().async_turn_on(**kwargs)
        else:
            await self.coordinator.async_refresh()
