"""Support for HIQ-Home blinds."""

from __future__ import annotations

from dataclasses import dataclass
from re import sub
from typing import Any

from homeassistant.components.cover import ATTR_POSITION
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.components.cover import CoverEntity
from homeassistant.components.cover import CoverEntityDescription
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import AREA_BLINDS
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
from .light import is_general_error_ok
from .models import HiqEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HIQ-Home blind based on a config entry."""
    coordinator: HiqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    blinds = find_blinds(
        coordinator,
    )
    if blinds is not None:
        async_add_entities(blinds)


@dataclass
class HiqCoverEntityDescription(CoverEntityDescription):
    """HIQ Cover Entity Description."""

    def __post_init__(self):
        """Defaults the translation_key to the sensor key."""
        self.has_entity_name = True
        self.translation_key = (
            self.translation_key
            or sub(r"c\d+\.", "", self.key).replace(".", "_").lower()
        )


def find_blinds(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqUpdateCover] | None:
    """Find blind objects in the plc vars.
    eg: c1000.bc00_blinds_position_00 and so on.
    """
    res: list[HiqUpdateCover] = []
    for key in coordinator.data.plc_info.plc_vars:
        if not (
            ".bc" in key
            and "_blinds_position" in key
            and is_general_error_ok(coordinator, key)
        ):
            continue
        dev_info = DeviceInfo(
            identifiers={(DOMAIN, key)},
            manufacturer=MANUFACTURER,
            name=f"Blind {key}",
            suggested_area=AREA_BLINDS,
            model=DEVICE_DESCRIPTION,
            configuration_url=MANUFACTURER_URL,
            entry_type=None,
            sw_version=DEVICE_SW_VERSION,
            hw_version=DEVICE_HW_VERSION,
            **coordinator.via_device_info,
        )
        var_sp, var_up, var_dn = _get_blind_vars(coordinator, key)
        res.append(
            HiqUpdateCover(
                coordinator,
                entity_description=HiqCoverEntityDescription(
                    key=key,
                    translation_key="blind",
                ),
                var_setpoint_name=var_sp,
                var_up_name=var_up,
                var_down_name=var_dn,
                dev_info=dev_info,
            )
        )
    if len(res) > 0:
        return res
    return None


def _get_blind_vars(
    coordinator: HiqDataUpdateCoordinator, var: str
) -> tuple[str, str, str]:
    """Find and return blind helper variables, "" if not existing.
    Input is the position var (eg: bc01_blinds_position_00)
    Returns the blind setpoint (bc01_blinds_setpoint_00),
    up output (bc01_qxs00_up) and down output (bc01_qxs00_dn).
    """
    blind_name = var.split("_")
    module, index = blind_name[0], blind_name[3]

    def existing(name: str) -> str:
        return name if name in coordinator.data.plc_info.plc_vars else ""

    return (
        existing(f"{module}_blinds_setpoint_{index}"),
        existing(f"{module}_qxs{index}_up"),
        existing(f"{module}_qxs{index}_dn"),
    )


class HiqUpdateCover(HiqEntity, CoverEntity):
    """Defines a Single HIQ-Home Blind."""

    _attr_device_class = CoverDeviceClass.BLIND
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _setpoint_var: str = ""
    _moving_up_var: str = ""
    _moving_dn_var: str = ""

    def __init__(
        self,
        coordinator: HiqDataUpdateCoordinator,
        entity_description: HiqCoverEntityDescription | None = None,
        unique_id: str | None = None,
        var_setpoint_name: str = "",
        var_up_name: str = "",
        var_down_name: str = "",
        dev_info: DeviceInfo = None,
    ) -> None:
        """Initialize HIQ-Home blind."""
        super().__init__(coordinator=coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = unique_id or entity_description.key
        self._attr_device_info = dev_info
        self._setpoint_var = var_setpoint_name
        self._moving_up_var = var_up_name
        self._moving_dn_var = var_down_name
        LOGGER.debug(self._attr_unique_id)
        coordinator.data.add_var(self._attr_unique_id, var_type=0)
        if self._moving_dn_var != "":
            coordinator.data.add_var(self._moving_dn_var, var_type=0)
        if self._moving_up_var != "":
            coordinator.data.add_var(self._moving_up_var, var_type=0)

    @property
    def is_closed(self) -> bool | None:
        """Return true if the cover is closed or None if the status is unknown."""
        res = self.coordinator.data.vars.get(self._attr_unique_id)
        if res is None or res.value in (None, "?"):
            return None
        return res.value == "100"

    def _is_output_on(self, var: str) -> bool:
        """Return true if the given motor output is on."""
        res = self.coordinator.data.vars.get(var)
        return res is not None and res.value == "1"

    @property
    def is_opening(self) -> bool:
        """Return true if the cover is actively opening."""
        return self._is_output_on(self._moving_up_var)

    @property
    def is_closing(self) -> bool:
        """Return true if the cover is actively closing."""
        return self._is_output_on(self._moving_dn_var)

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        res = self.coordinator.get_value(self._attr_unique_id)
        if res is None:
            return None
        return int(100 - int(res))

    async def _write_setpoint(self, value: str) -> None:
        """Write the blind setpoint (closed percentage, -1 stops), if it exists."""
        if self._setpoint_var != "":
            await self.coordinator.cybro.write_var(self._setpoint_var, value)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Move the cover up."""
        await self._write_setpoint("0")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Move the cover down."""
        await self._write_setpoint("100")

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._write_setpoint("-1")

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self._write_setpoint(str(100 - int(kwargs[ATTR_POSITION])))

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
