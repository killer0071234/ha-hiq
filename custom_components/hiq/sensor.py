"""Support for HIQ-Home sensors."""
from __future__ import annotations

from re import search, sub
from collections.abc import Callable
from dataclasses import dataclass

from typing import Any

from datetime import datetime

from cybro import VarType
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    AREA_ENERGY,
    AREA_SYSTEM,
    AREA_WEATHER,
    AREA_CLIMATE,
    ATTR_DESCRIPTION,
    DEVICE_DESCRIPTION,
    DEVICE_HW_VERSION,
    DEVICE_SW_VERSION,
    DOMAIN,
    LOGGER,
    MANUFACTURER,
    MANUFACTURER_URL,
)
from .coordinator import HiqDataUpdateCoordinator
from .light import is_general_error_ok
from .models import HiqEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HIQ-Home sensor based on a config entry."""
    coordinator: HiqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sys_tags = add_system_tags(
        coordinator,
    )
    if sys_tags is not None:
        async_add_entities(sys_tags)

    temps = find_temperatures(
        coordinator,
    )
    if temps is not None:
        async_add_entities(temps)

    # weather = find_weather(coordinator)
    # if weather is not None:
    #    async_add_entities(weather)

    power_meter = find_power_meter(
        coordinator,
    )
    if power_meter is not None:
        async_add_entities(power_meter)

    th_tags = add_th_tags(
        coordinator,
    )
    if th_tags is not None:
        async_add_entities(th_tags)

    hvac_tags = add_hvac_tags(
        coordinator,
    )
    if hvac_tags is not None:
        async_add_entities(hvac_tags)


@dataclass
class HiqSensorEntityDescription(SensorEntityDescription):
    """HIQ Sensor Entity Description."""

    value_conversion_function: Callable[[Any], str] | None = None

    def __post_init__(self):
        """Defaults the translation_key to the sensor key."""
        self.has_entity_name = True
        self.translation_key = (
            self.translation_key
            or sub(r"c\d+\.", "", self.key).replace(".", "_").lower()
        )


def add_system_tags(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqSensorEntity] | None:
    """Find system tags in the plc vars.
    eg: c1000.scan_time and so on.
    """
    res: list[HiqSensorEntity] = []
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
    # add system vars
    res.append(
        HiqSensorEntity(
            coordinator=coordinator,
            entity_description=HiqSensorEntityDescription(
                key=f"{var_prefix}sys.ip_port",
                # state_class=SensorStateClass.MEASUREMENT, # set to None for string sensors (currently the only one)
                entity_category=EntityCategory.DIAGNOSTIC,
                entity_registry_enabled_default=False,
            ),
            var_type=VarType.STR,
            val_fact=1.0,
            dev_info=dev_info,
        )
    )
    # find different plc diagnostic vars
    for key in coordinator.data.plc_info.plc_vars:
        if key.find(var_prefix) != -1:
            if key in (f"{var_prefix}scan_time", f"{var_prefix}scan_time_max"):
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        entity_description=HiqSensorEntityDescription(
                            key=key,
                            native_unit_of_measurement=UnitOfTime.MILLISECONDS,
                            state_class=SensorStateClass.MEASUREMENT,
                            entity_category=EntityCategory.DIAGNOSTIC,
                            entity_registry_enabled_default=False,
                            suggested_display_precision=0,
                        ),
                        var_type=VarType.INT,
                        val_fact=1.0,
                        dev_info=dev_info,
                    )
                )
            elif key in (f"{var_prefix}cybro_uptime", f"{var_prefix}operating_hours"):
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        entity_description=HiqSensorEntityDescription(
                            key=key,
                            native_unit_of_measurement=UnitOfTime.HOURS,
                            device_class=SensorDeviceClass.DURATION,
                            state_class=SensorStateClass.MEASUREMENT,
                            entity_category=EntityCategory.DIAGNOSTIC,
                            suggested_display_precision=0,
                        ),
                        var_type=VarType.INT,
                        val_fact=1.0,
                        dev_info=dev_info,
                    )
                )
            elif key in (f"{var_prefix}scan_frequency"):
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        entity_description=HiqSensorEntityDescription(
                            key=key,
                            native_unit_of_measurement=UnitOfFrequency.HERTZ,
                            state_class=SensorStateClass.MEASUREMENT,
                            entity_category=EntityCategory.DIAGNOSTIC,
                            entity_registry_enabled_default=False,
                            suggested_display_precision=0,
                        ),
                        var_type=VarType.INT,
                        val_fact=1.0,
                        dev_info=dev_info,
                    )
                )
            elif (
                key.find("iex_power_supply") != -1
                or key.find("cybro_power_supply") != -1
            ):
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        entity_description=HiqSensorEntityDescription(
                            key=key,
                            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                            device_class=SensorDeviceClass.VOLTAGE,
                            state_class=SensorStateClass.MEASUREMENT,
                            entity_category=EntityCategory.DIAGNOSTIC,
                            entity_registry_enabled_default=False,
                            suggested_display_precision=1,
                        ),
                        var_type=VarType.FLOAT,
                        val_fact=0.1,
                        dev_info=dev_info,
                    )
                )

    if len(res) > 0:
        return res
    return None


def find_temperatures(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqSensorEntity] | None:
    """Find simple temperature objects in the plc vars.
    eg: c1000.ts00_temperature and so on.
    temperatures and humidity of thermostat objects are joined to the thermostat object.
    """
    res: list[HiqSensorEntity] = []
    dev_info = DeviceInfo(
        identifiers={(DOMAIN, f"{coordinator.data.plc_info.nad}.temperatures")},
        manufacturer=MANUFACTURER,
        name=f"c{coordinator.cybro.nad} temperatures",
        suggested_area=AREA_WEATHER,
        model=DEVICE_DESCRIPTION,
        configuration_url=MANUFACTURER_URL,
        entry_type=None,
        sw_version=DEVICE_SW_VERSION,
        hw_version=DEVICE_HW_VERSION,
        via_device=(DOMAIN, coordinator.cybro.nad),
    )

    for key in coordinator.data.plc_info.plc_vars:
        if key.find(".op") != -1 or key.find(".ts") != -1 or key.find(".fc") != -1:
            if is_general_error_ok(coordinator, key):
                if key.find("_temperature") != -1:
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            entity_description=HiqSensorEntityDescription(
                                key=key,
                                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                                device_class=SensorDeviceClass.TEMPERATURE,
                                state_class=SensorStateClass.MEASUREMENT,
                                suggested_display_precision=1,
                            ),
                            var_type=VarType.FLOAT,
                            val_fact=0.1,
                            dev_info=dev_info,
                        )
                    )
                elif key.find("_humidity") != -1:
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            entity_description=HiqSensorEntityDescription(
                                key=key,
                                native_unit_of_measurement=PERCENTAGE,
                                device_class=SensorDeviceClass.HUMIDITY,
                                state_class=SensorStateClass.MEASUREMENT,
                                suggested_display_precision=0,
                            ),
                            var_type=VarType.FLOAT,
                            val_fact=1.0,
                            dev_info=dev_info,
                        )
                    )

    if len(res) > 0:
        return res
    return None


def find_weather(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqSensorEntity] | None:
    """Find simple temperature objects in the plc vars.
    eg: c1000.weather_temperature and so on.
    """
    res: list[HiqSensorEntity] = []
    var_prefix = f"c{coordinator.data.plc_info.nad}.weather_"
    dev_info = DeviceInfo(
        identifiers={(DOMAIN, var_prefix)},
        manufacturer=MANUFACTURER,
        name=f"c{coordinator.cybro.nad} weather",
        suggested_area=AREA_WEATHER,
        model=DEVICE_DESCRIPTION,
        configuration_url=MANUFACTURER_URL,
        entry_type=None,
        sw_version=DEVICE_SW_VERSION,
        hw_version=DEVICE_HW_VERSION,
        via_device=(DOMAIN, coordinator.cybro.nad),
    )

    for key in coordinator.data.plc_info.plc_vars:
        if key.find(var_prefix) != -1:
            if is_general_error_ok(coordinator, key):
                if key.find("_temperature") != -1:
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            entity_description=HiqSensorEntityDescription(
                                key=key,
                                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                                device_class=SensorDeviceClass.TEMPERATURE,
                                state_class=SensorStateClass.MEASUREMENT,
                                # entity_category=EntityCategory.DIAGNOSTIC,
                                suggested_display_precision=1,
                            ),
                            var_type=VarType.FLOAT,
                            val_fact=0.1,
                            dev_info=dev_info,
                        )
                    )
                elif key.find("_humidity") != -1:
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            entity_description=HiqSensorEntityDescription(
                                key=key,
                                native_unit_of_measurement=PERCENTAGE,
                                device_class=SensorDeviceClass.HUMIDITY,
                                state_class=SensorStateClass.MEASUREMENT,
                                # entity_category=EntityCategory.DIAGNOSTIC,
                                suggested_display_precision=0,
                            ),
                            var_type=VarType.FLOAT,
                            val_fact=1.0,
                            dev_info=dev_info,
                        )
                    )
                elif key.find("_wind_speed") != -1:
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            entity_description=HiqSensorEntityDescription(
                                key=key,
                                native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
                                device_class=SensorDeviceClass.WIND_SPEED,
                                state_class=SensorStateClass.MEASUREMENT,
                                # entity_category=EntityCategory.DIAGNOSTIC,
                                suggested_display_precision=1,
                            ),
                            val_fact=0.1,
                            var_type=VarType.FLOAT,
                            dev_info=dev_info,
                        )
                    )

    if len(res) > 0:
        return res
    return None


def find_power_meter(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqSensorEntity] | None:
    """Find power meter objects in the plc vars.
    eg: c1000.power_meter_power and so on.
    """
    res: list[HiqSensorEntity] = []
    var_prefix = f"c{coordinator.data.plc_info.nad}.power_meter"
    dev_info = DeviceInfo(
        identifiers={(DOMAIN, var_prefix)},
        manufacturer=MANUFACTURER,
        name=f"c{coordinator.cybro.nad} power meter",
        suggested_area=AREA_ENERGY,
        model=DEVICE_DESCRIPTION,
        configuration_url=MANUFACTURER_URL,
        entry_type=None,
        sw_version=DEVICE_SW_VERSION,
        hw_version=DEVICE_HW_VERSION,
        via_device=(DOMAIN, coordinator.cybro.nad),
    )
    for key in coordinator.data.plc_info.plc_vars:
        if key.find(var_prefix) != -1:
            if key.find("_power") != -1:
                if _is_power_meter_ok(coordinator, key):
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            entity_description=HiqSensorEntityDescription(
                                key=key,
                                native_unit_of_measurement=UnitOfPower.WATT,
                                device_class=SensorDeviceClass.POWER,
                                state_class=SensorStateClass.MEASUREMENT,
                                suggested_display_precision=0,
                            ),
                            var_type=VarType.FLOAT,
                            val_fact=1.0,
                            dev_info=dev_info,
                        )
                    )
            elif key.find("_voltage") != -1:
                if _is_power_meter_ok(coordinator, key):
                    fact = 1.0
                    val = coordinator.data.vars.get(key, None)
                    if val is not None and float(val.value.replace(",", "")) > 300:
                        fact = 0.1
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            entity_description=HiqSensorEntityDescription(
                                key=key,
                                native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                                device_class=SensorDeviceClass.VOLTAGE,
                                state_class=SensorStateClass.MEASUREMENT,
                                entity_registry_enabled_default=False,
                                suggested_display_precision=0,
                            ),
                            var_type=VarType.FLOAT,
                            val_fact=fact,
                            dev_info=dev_info,
                        )
                    )
            elif key.find("_current") != -1:
                if _is_power_meter_ok(coordinator, key):
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            entity_description=HiqSensorEntityDescription(
                                key=key,
                                native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
                                device_class=SensorDeviceClass.CURRENT,
                                state_class=SensorStateClass.MEASUREMENT,
                                entity_registry_enabled_default=False,
                                suggested_display_precision=0,
                            ),
                            var_type=VarType.FLOAT,
                            val_fact=1.0,
                            dev_info=dev_info,
                        )
                    )
            elif key in (f"{var_prefix}_energy", f"{var_prefix}_energy_real"):
                if _is_power_meter_ok(coordinator, key):
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            entity_description=HiqSensorEntityDescription(
                                key=key,
                                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                                device_class=SensorDeviceClass.ENERGY,
                                state_class=SensorStateClass.TOTAL_INCREASING,
                                suggested_display_precision=0,
                            ),
                            var_type=VarType.FLOAT,
                            val_fact=1.0,
                            dev_info=dev_info,
                        )
                    )
            elif key.find(f"{var_prefix}_energy_watthours") != -1:
                if _is_power_meter_ok(coordinator, key):
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            entity_description=HiqSensorEntityDescription(
                                key=key,
                                native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
                                device_class=SensorDeviceClass.ENERGY,
                                state_class=SensorStateClass.TOTAL_INCREASING,
                                entity_registry_enabled_default=False,
                                suggested_display_precision=0,
                            ),
                            var_type=VarType.FLOAT,
                            val_fact=1.0,
                            dev_info=dev_info,
                        )
                    )

    if len(res) > 0:
        return res
    return None


def _is_power_meter_ok(coordinator: HiqDataUpdateCoordinator, var: str):
    ge_names = var.split("_")
    if ge_names is None:
        return False
    ge_name = f"{ge_names[0]}_meter_error"
    coordinator.data.add_var(ge_name)
    ge_val = coordinator.data.vars.get(ge_name, None)
    if ge_val is None:
        return False
    LOGGER.debug("%s -> %s", ge_name, ge_val.value)
    return bool(ge_val.value == "0")


def add_th_tags(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqSensorEntity] | None:
    """Find temperature sensors for thermostat tags in the plc vars.
    eg: c1000.th00_floor_tmp and so on.
    """
    res: list[HiqSensorEntity] = []

    # find different thermostat vars
    for key in coordinator.data.plc_info.plc_vars:
        unique_id = key
        # identifier is cNAD.thNR
        grp = search(r"c\d+\.th\d+", key)
        if grp:
            unique_id = grp.group()
        dev_info = DeviceInfo(
            identifiers={(coordinator.cybro.nad, f"{unique_id} thermostat")},
            manufacturer=MANUFACTURER,
            name=f"{unique_id} thermostat",
            suggested_area=AREA_CLIMATE,
            via_device=(DOMAIN, coordinator.cybro.nad),
        )

        # get temperature
        if key == f"{unique_id}_temperature":
            if is_general_error_ok(coordinator, key):
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        entity_description=HiqSensorEntityDescription(
                            key=key,
                            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                            device_class=SensorDeviceClass.TEMPERATURE,
                            state_class=SensorStateClass.MEASUREMENT,
                            suggested_display_precision=1,
                        ),
                        var_type=VarType.FLOAT,
                        val_fact=0.1,
                        dev_info=dev_info,
                    )
                )
        elif key == f"{unique_id}_temperature_1":
            if is_general_error_ok(coordinator, key):
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        entity_description=HiqSensorEntityDescription(
                            key=key,
                            translation_key="temperature_1",
                            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                            device_class=SensorDeviceClass.TEMPERATURE,
                            state_class=SensorStateClass.MEASUREMENT,
                            suggested_display_precision=1,
                        ),
                        var_type=VarType.FLOAT,
                        val_fact=0.1,
                        dev_info=dev_info,
                    )
                )
        # get humidity of thermostat
        elif key == f"{unique_id}_humidity":
            if is_general_error_ok(coordinator, key):
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        entity_description=HiqSensorEntityDescription(
                            key=key,
                            native_unit_of_measurement=PERCENTAGE,
                            device_class=SensorDeviceClass.HUMIDITY,
                            state_class=SensorStateClass.MEASUREMENT,
                            suggested_display_precision=0,
                        ),
                        var_type=VarType.FLOAT,
                        val_fact=1.0,
                        dev_info=dev_info,
                    )
                )
        # get light sensor of thermostat
        elif key == f"{unique_id}_light_sensor":
            if is_general_error_ok(coordinator, key):
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        entity_description=HiqSensorEntityDescription(
                            key=key,
                            translation_key="light_sensor",
                            native_unit_of_measurement=PERCENTAGE,
                            # device_class=SensorDeviceClass.HUMIDITY,
                            state_class=SensorStateClass.MEASUREMENT,
                            entity_registry_enabled_default=False,
                            suggested_display_precision=1,
                        ),
                        var_type=VarType.FLOAT,
                        val_fact=0.097751711,  # sensor is returning 0..1023 = 0..100%
                        dev_info=dev_info,
                    )
                )
        # get remaining max time
        elif key == f"{unique_id}_max_timer":
            if is_general_error_ok(coordinator, key):
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        entity_description=HiqSensorEntityDescription(
                            key=key,
                            translation_key="max_timer_remain",
                            native_unit_of_measurement=UnitOfTime.SECONDS,
                            device_class=SensorDeviceClass.DURATION,
                            state_class=SensorStateClass.MEASUREMENT,
                            entity_registry_enabled_default=False,
                            suggested_display_precision=0,
                        ),
                        var_type=VarType.INT,
                        val_fact=1.0,
                        dev_info=dev_info,
                    )
                )

    if len(res) > 0:
        return res
    return None


def add_hvac_tags(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqSensorEntity] | None:
    """Find and add HVAC tags in the plc vars.
    eg: c1000.outdoor_temperature and so on.
    """
    res: list[HiqSensorEntity] = []

    def _is_enabled(tag: str) -> bool:
        """Get enable state of variable."""
        value = coordinator.data.vars.get(tag, None)
        if value is None:
            return False
        LOGGER.debug("%s -> %s", tag, value.value)
        return bool(value.value == "1")

    # find different hvac related vars
    for key in coordinator.data.plc_info.plc_vars:
        unique_id = key
        # identifier is cNAD
        grp = search(r"c\d+", key)
        if grp:
            unique_id = grp.group()
        dev_info = DeviceInfo(
            identifiers={(coordinator.cybro.nad, f"{unique_id} HVAC")},
            manufacturer=MANUFACTURER,
            name=f"{unique_id} HVAC",
            suggested_area=AREA_CLIMATE,
            via_device=(DOMAIN, coordinator.cybro.nad),
        )

        # get temperature(s)
        if key == f"{unique_id}.outdoor_temperature":
            res.append(
                HiqSensorEntity(
                    coordinator=coordinator,
                    entity_description=HiqSensorEntityDescription(
                        key=key,
                        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                        device_class=SensorDeviceClass.TEMPERATURE,
                        state_class=SensorStateClass.MEASUREMENT,
                        entity_registry_enabled_default=_is_enabled(
                            f"c{coordinator.cybro.nad}.outdoor_temperature_enable"
                        ),
                        suggested_display_precision=1,
                    ),
                    var_type=VarType.FLOAT,
                    val_fact=0.1,
                    dev_info=dev_info,
                )
            )
        if key == f"{unique_id}.wall_temperature":
            res.append(
                HiqSensorEntity(
                    coordinator=coordinator,
                    entity_description=HiqSensorEntityDescription(
                        key=key,
                        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                        device_class=SensorDeviceClass.TEMPERATURE,
                        state_class=SensorStateClass.MEASUREMENT,
                        entity_registry_enabled_default=_is_enabled(
                            f"c{coordinator.cybro.nad}.wall_temperature_enable"
                        ),
                        suggested_display_precision=1,
                    ),
                    var_type=VarType.FLOAT,
                    val_fact=0.1,
                    dev_info=dev_info,
                )
            )
        if key == f"{unique_id}.water_temperature":
            res.append(
                HiqSensorEntity(
                    coordinator=coordinator,
                    entity_description=HiqSensorEntityDescription(
                        key=key,
                        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                        device_class=SensorDeviceClass.TEMPERATURE,
                        state_class=SensorStateClass.MEASUREMENT,
                        entity_registry_enabled_default=_is_enabled(
                            f"c{coordinator.cybro.nad}.water_temperature_enable"
                        ),
                        suggested_display_precision=1,
                    ),
                    var_type=VarType.FLOAT,
                    val_fact=0.1,
                    dev_info=dev_info,
                )
            )
        if key == f"{unique_id}.auxilary_temperature":
            res.append(
                HiqSensorEntity(
                    coordinator=coordinator,
                    entity_description=HiqSensorEntityDescription(
                        key=key,
                        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                        device_class=SensorDeviceClass.TEMPERATURE,
                        state_class=SensorStateClass.MEASUREMENT,
                        entity_registry_enabled_default=_is_enabled(
                            f"c{coordinator.cybro.nad}.auxilary_temperature_enable"
                        ),
                        suggested_display_precision=1,
                    ),
                    var_type=VarType.FLOAT,
                    val_fact=0.1,
                    dev_info=dev_info,
                )
            )

    if len(res) > 0:
        return res
    return None


class HiqSensorEntity(HiqEntity, SensorEntity):
    """Defines a HIQ-Home sensor entity."""

    _var_type: VarType = VarType.INT
    _val_fact: float = 1.0

    def __init__(
        self,
        coordinator: HiqDataUpdateCoordinator,
        entity_description: HiqSensorEntityDescription | None = None,
        unique_id: str | None = None,
        var_type: VarType = VarType.INT,
        val_fact: float = 1.0,
        dev_info: DeviceInfo = None,
    ) -> None:
        """Initialize a HIQ-Home sensor entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = unique_id or entity_description.key
        self._attr_device_info = dev_info
        LOGGER.debug(self._attr_unique_id)
        coordinator.data.add_var(self._attr_unique_id, var_type=var_type)
        self._var_type = var_type
        self._val_fact = val_fact

    @property
    def native_value(self) -> datetime | StateType | None:
        """Return the state of the sensor."""
        return self.coordinator.get_value(
            self._attr_unique_id, self._val_fact, self.suggested_display_precision
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        try:
            desc = self.coordinator.data.vars[self._attr_unique_id].description
        except KeyError:
            desc = "?"
        return {
            ATTR_DESCRIPTION: desc,
        }
