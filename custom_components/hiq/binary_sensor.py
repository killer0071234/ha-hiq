"""Support for HIQ-Home binary sensor."""
from __future__ import annotations
from re import search
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import AREA_CLIMATE
from .const import AREA_SYSTEM
from .const import ATTR_DESCRIPTION
from .const import CONF_IGNORE_GENERAL_ERROR
from .const import DEVICE_DESCRIPTION
from .const import DEVICE_HW_VERSION
from .const import DEVICE_SW_VERSION
from .const import DOMAIN
from .const import LOGGER
from .const import MANUFACTURER
from .const import MANUFACTURER_URL
from .coordinator import HiqDataUpdateCoordinator
from .models import HiqEntity
from .light import is_general_error_ok


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    variable_name: str = "",
) -> None:
    """Set up a HIQ binary sensor based on a config entry."""
    coordinator: HiqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    ignore_general_error = entry.options.get(CONF_IGNORE_GENERAL_ERROR, False)

    sys_tags = add_system_tags(
        coordinator,
        ignore_general_error,
    )
    if sys_tags is not None:
        async_add_entities(sys_tags)

    th_tags = add_th_tags(
        coordinator,
        ignore_general_error,
    )
    if th_tags is not None:
        async_add_entities(th_tags)


def add_system_tags(
    coordinator: HiqDataUpdateCoordinator,
    add_all: bool = False,
) -> list[HiqBinarySensor] | None:
    """Find system tags in the plc vars.
    eg: c1000.scan_time and so on.
    """
    res: list[HiqBinarySensor] = []
    var_prefix = f"c{coordinator.cybro.nad}."
    dev_info = DeviceInfo(
        identifiers={(DOMAIN, coordinator.cybro.nad)},
        manufacturer=MANUFACTURER,
        name=f"c{coordinator.cybro.nad} diagnostic",
        suggested_area=AREA_SYSTEM,
        model=DEVICE_DESCRIPTION,
        configuration_url=MANUFACTURER_URL,
        entry_type=None,
        sw_version=DEVICE_SW_VERSION,
        hw_version=DEVICE_HW_VERSION,
    )

    # find different plc diagnostic vars
    for key in coordinator.data.plc_info.plc_vars:
        if key.find(var_prefix) != -1:
            if key in (f"{var_prefix}scan_overrun", f"{var_prefix}retentive_fail"):
                res.append(
                    HiqBinarySensor(
                        coordinator,
                        key,
                        attr_entity_category=EntityCategory.DIAGNOSTIC,
                        attr_device_class=BinarySensorDeviceClass.PROBLEM,
                        dev_info=dev_info,
                    )
                )
            if key.find("general_error") != -1:
                res.append(
                    HiqBinarySensor(
                        coordinator,
                        key,
                        attr_entity_category=EntityCategory.DIAGNOSTIC,
                        attr_device_class=BinarySensorDeviceClass.PROBLEM,
                        dev_info=dev_info,
                    )
                )

    if len(res) > 0:
        return res
    return None


def add_th_tags(
    coordinator: HiqDataUpdateCoordinator,
    add_all: bool = False,
) -> list[HiqBinarySensor] | None:
    """Find binary sensors for thermostat tags in the plc vars.
    eg: c1000.th00_ix00 and so on.
    """
    res: list[HiqBinarySensor] = []

    # find different plc diagnostic vars
    for key in coordinator.data.plc_info.plc_vars:
        # get window contact input
        if search(r"c\d+\.th\d+_ix00", key):
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                unique_id = key
                # identifier is cNAD.thNR
                grp = search(r"c\d+\.th\d+", key)
                if grp:
                    unique_id = grp.group()
                res.append(
                    HiqBinarySensor(
                        coordinator,
                        var_name=f"thermostat {unique_id} window",
                        unique_id=key,
                        value_on="0",
                        attr_device_class=BinarySensorDeviceClass.WINDOW,
                        dev_info=DeviceInfo(
                            identifiers={
                                (coordinator.cybro.nad, f"thermostat {unique_id}")
                            },
                            manufacturer=MANUFACTURER,
                            name=f"thermostat {unique_id}",
                            suggested_area=AREA_CLIMATE,
                            via_device=(DOMAIN, coordinator.cybro.nad),
                        ),
                    )
                )
        # get heating output
        if search(r"c\d+\.th\d+_output", key):
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                unique_id = key
                # identifier is cNAD.thNR
                grp = search(r"c\d+\.th\d+", key)
                if grp:
                    unique_id = grp.group()
                res.append(
                    HiqBinarySensor(
                        coordinator,
                        var_name=f"thermostat {unique_id} output",
                        unique_id=key,
                        # DeviceClass.HEAT as default, could also be cool but most of the devices are used for heating
                        # attr_device_class=BinarySensorDeviceClass.HEAT,
                        dev_info=DeviceInfo(
                            identifiers={
                                (coordinator.cybro.nad, f"thermostat {unique_id}")
                            },
                            manufacturer=MANUFACTURER,
                            name=f"thermostat {unique_id}",
                            suggested_area=AREA_CLIMATE,
                            via_device=(DOMAIN, coordinator.cybro.nad),
                        ),
                    )
                )

    if len(res) > 0:
        return res
    return None


class HiqBinarySensor(HiqEntity, BinarySensorEntity):
    """An entity using CoordinatorEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available

    """

    def __init__(
        self,
        coordinator: HiqDataUpdateCoordinator,
        var_name: str = "",
        unique_id: str | None = None,
        value_on: str = "1",
        attr_entity_category: EntityCategory = None,
        attr_device_class: BinarySensorDeviceClass = None,
        enabled: bool = True,
        dev_info: DeviceInfo = None,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator=coordinator)
        if var_name == "":
            return
        self._attr_name = var_name
        self._attr_unique_id = unique_id or var_name
        self._attr_entity_category = attr_entity_category
        self._attr_device_class = attr_device_class
        self._attr_device_info = dev_info
        if enabled is False:
            self._attr_entity_registry_enabled_default = False
        self._value_on = value_on
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
            name=f"PLC {self.coordinator.cybro.nad}",
            model=DEVICE_DESCRIPTION,
        )

    @property
    def is_on(self) -> bool | None:
        """Return entity state."""
        if self._attr_unique_id in self.coordinator.data.vars:
            self._attr_available = True
            return (
                self.coordinator.data.vars[self._attr_unique_id].value == self._value_on
            )
        self._attr_available = False
        return None

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
