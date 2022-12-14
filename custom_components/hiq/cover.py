"""Support for HIQ-Home blinds."""
from __future__ import annotations

from typing import Any

from homeassistant.components.cover import ATTR_POSITION
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.components.cover import CoverEntity
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import AREA_BLINDS
from .const import ATTR_DESCRIPTION
from .const import CONF_IGNORE_GENERAL_ERROR
from .const import DEVICE_DESCRIPTION
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
        coordinator, entry.options.get(CONF_IGNORE_GENERAL_ERROR, False)
    )
    if blinds is not None:
        async_add_entities(blinds)


def find_blinds(
    coordinator: HiqDataUpdateCoordinator,
    add_all: bool,
) -> list[HiqUpdateCover] | None:
    """Find blind objects in the plc vars.
    eg: c1000.bc00_blinds_position_00 and so on
    """
    res: list[HiqUpdateCover] = []
    for key in coordinator.data.plc_info.plc_vars:
        if key.find(".bc") != -1 and key.find("_blinds_position") != -1:
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                dev_info = DeviceInfo(
                    identifiers={(DOMAIN, key)},
                    manufacturer=MANUFACTURER,
                    default_name=f"Blind {key}",
                    suggested_area=AREA_BLINDS,
                    model=DEVICE_DESCRIPTION,
                    configuration_url=MANUFACTURER_URL,
                )
                var_sp = _get_blind_var(coordinator, key, 0)
                var_up = _get_blind_var(coordinator, key, 1)
                var_dn = _get_blind_var(coordinator, key, 2)
                res.append(
                    HiqUpdateCover(
                        coordinator,
                        key,
                        var_sp,
                        var_up,
                        var_dn,
                        enabled=ge_ok,
                        dev_info=dev_info,
                    )
                )
    if len(res) > 0:
        return res
    return None


def _get_blind_var(
    coordinator: HiqDataUpdateCoordinator, var: str, type: int = 0
) -> str:
    """Find and return blind helper variables.
    Input is the position var (eg: bc01_blinds_position_00)
    type = 0: blind setpoint (bc01_blinds_setpoint_00)
    type = 1: blind up output (bc01_qxs00_up)
    type = 2: blind down output (bc01_qxs00_dn)
    """
    blind_name = var.split("_")
    if blind_name is None:
        return ""
    if type == 0:
        name_var = f"{blind_name[0]}_blinds_setpoint_{blind_name[3]}"
    elif type == 1:
        name_var = f"{blind_name[0]}_qxs{blind_name[3]}_up"
    elif type == 2:
        name_var = f"{blind_name[0]}_qxs{blind_name[3]}_dn"
    if name_var in coordinator.data.plc_info.plc_vars:
        return name_var
    return ""


class HiqUpdateCover(HiqEntity, CoverEntity):
    """Defines a Single HIQ-Home Blind."""

    _setpoint_var: str = ""
    _moving_up_var: str = ""
    _moving_dn_var: str = ""

    def __init__(
        self,
        coordinator: HiqDataUpdateCoordinator,
        var_name: str = "",
        var_setpoint_name: str = "",
        var_up_name: str = "",
        var_down_name: str = "",
        enabled: bool = True,
        dev_info: DeviceInfo = None,
    ) -> None:
        """Initialize HIQ-Home blind."""
        super().__init__(coordinator=coordinator)
        if var_name == "":
            return
        self._attr_unique_id = var_name
        self._attr_name = f"Blind {var_name}"
        self._attr_device_info = dev_info
        self._setpoint_var = var_setpoint_name
        self._moving_up_var = var_up_name
        self._moving_dn_var = var_down_name
        if enabled is False:
            self._attr_entity_registry_enabled_default = False
        LOGGER.debug(self._attr_unique_id)
        coordinator.data.add_var(self._attr_unique_id, var_type=0)
        if self._moving_dn_var != "":
            coordinator.data.add_var(self._moving_dn_var, var_type=0)
        if self._moving_up_var != "":
            coordinator.data.add_var(self._moving_up_var, var_type=0)

    @property
    def device_info(self):
        """Return the device info."""
        if self._attr_device_info is not None:
            return self._attr_device_info
        return DeviceInfo(
            identifiers={(DOMAIN, self.platform.config_entry.unique_id)},
            manufacturer=MANUFACTURER,
            configuration_url=MANUFACTURER_URL,
            name=f"c{self.coordinator.cybro.nad} blind channel",
            model=DEVICE_DESCRIPTION,
        )

    @property
    def is_closed(self) -> bool | None:
        """Return true if the cover is closed or None if the status is unknown."""
        res = self.coordinator.data.vars.get(self._attr_unique_id, None)
        if res is None or res == "?":
            return None
        return bool(res.value == "100")

    @property
    def is_opening(self) -> bool:
        """Return true if the cover is actively opening."""
        if self._moving_up_var != "":
            res = self.coordinator.data.vars.get(self._moving_up_var, None)
            if res is None or res == "?":
                return False
            return bool(res.value == "1")
        return False

    @property
    def is_closing(self) -> bool:
        """Return true if the cover is actively closing."""
        if self._moving_dn_var != "":
            res = self.coordinator.data.vars.get(self._moving_dn_var, None)
            if res is None or res == "?":
                return False
            return bool(res.value == "1")
        return False

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        res = self.coordinator.data.vars.get(self._attr_unique_id, None)
        if res is None or res == "?":
            return None
        return int(100 - int(res.value))

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt."""
        return None

    @property
    def device_class(self) -> CoverDeviceClass | None:
        """Return the class of this sensor."""
        return CoverDeviceClass.BLIND

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Move the cover up."""
        if self._setpoint_var != "":
            await self.coordinator.cybro.write_var(self._setpoint_var, "0")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Move the cover down."""
        if self._setpoint_var != "":
            await self.coordinator.cybro.write_var(self._setpoint_var, "100")

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        if self._setpoint_var != "":
            await self.coordinator.cybro.write_var(self._setpoint_var, "-1")

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        if self._setpoint_var != "":
            pos = 100 - int(position)
            await self.coordinator.cybro.write_var(self._setpoint_var, str(pos))

    @property
    def available(self) -> bool:
        """Return if this light is available or not."""
        res = self.coordinator.data.vars.get(self._attr_unique_id, None)
        if res is None:
            return False
        return res.value != "?"

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
