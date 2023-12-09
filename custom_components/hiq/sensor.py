"""Support for HIQ-Home sensors."""
from __future__ import annotations

from re import search

from datetime import datetime

from cybro import VarType
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
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
    CONF_IGNORE_GENERAL_ERROR,
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

    ignore_general_error = entry.options.get(CONF_IGNORE_GENERAL_ERROR, False)

    sys_tags = add_system_tags(
        coordinator,
        ignore_general_error,
    )
    if sys_tags is not None:
        async_add_entities(sys_tags)

    temps = find_temperatures(
        coordinator,
        ignore_general_error,
    )
    if temps is not None:
        async_add_entities(temps)

    # weather = find_weather(coordinator)
    # if weather is not None:
    #    async_add_entities(weather)

    power_meter = find_power_meter(
        coordinator,
        ignore_general_error,
    )
    if power_meter is not None:
        async_add_entities(power_meter)

    th_tags = add_th_tags(
        coordinator,
        ignore_general_error,
    )
    if th_tags is not None:
        async_add_entities(th_tags)

    hvac_tags = add_hvac_tags(
        coordinator,
        ignore_general_error,
    )
    if hvac_tags is not None:
        async_add_entities(hvac_tags)


def add_system_tags(
    coordinator: HiqDataUpdateCoordinator,
    add_all: bool = False,
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
            var_name=f"{var_prefix}sys.ip_port",
            unique_id=None,
            var_description="",
            var_unit=None,
            var_type=VarType.STR,
            attr_entity_category=EntityCategory.DIAGNOSTIC,
            attr_device_class=None,
            val_fact=1.0,
            display_precision=None,
            enabled=False,
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
                        var_name=key,
                        unique_id=None,
                        var_description="",
                        var_unit=UnitOfTime.MILLISECONDS,
                        var_type=VarType.INT,
                        attr_entity_category=EntityCategory.DIAGNOSTIC,
                        attr_device_class=None,
                        val_fact=1.0,
                        display_precision=0,
                        enabled=add_all,
                        dev_info=dev_info,
                    )
                )
            elif key in (f"{var_prefix}cybro_uptime", f"{var_prefix}operating_hours"):
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        var_name=key,
                        unique_id=None,
                        var_description="",
                        var_unit=UnitOfTime.MINUTES,
                        var_type=VarType.INT,
                        attr_entity_category=EntityCategory.DIAGNOSTIC,
                        attr_device_class=SensorDeviceClass.DURATION,
                        val_fact=1.0,
                        display_precision=0,
                        enabled=add_all,
                        dev_info=dev_info,
                    )
                )
            elif key in (f"{var_prefix}scan_frequency"):
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        var_name=key,
                        unique_id=None,
                        var_description="",
                        var_unit=UnitOfFrequency.HERTZ,
                        var_type=VarType.INT,
                        attr_entity_category=EntityCategory.DIAGNOSTIC,
                        attr_device_class=None,
                        val_fact=1.0,
                        display_precision=0,
                        enabled=add_all,
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
                        var_name=key,
                        unique_id=None,
                        var_description="",
                        var_unit=UnitOfElectricPotential.VOLT,
                        var_type=VarType.FLOAT,
                        attr_entity_category=EntityCategory.DIAGNOSTIC,
                        attr_device_class=SensorDeviceClass.VOLTAGE,
                        val_fact=0.1,
                        display_precision=1,
                        enabled=add_all,
                        dev_info=dev_info,
                    )
                )

    if len(res) > 0:
        return res
    return None


def find_temperatures(
    coordinator: HiqDataUpdateCoordinator,
    add_all: bool = False,
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
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                if key.find("_temperature") != -1:
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            var_name=key,
                            unique_id=None,
                            var_description="",
                            var_unit=UnitOfTemperature.CELSIUS,
                            var_type=VarType.FLOAT,
                            attr_entity_category=None,
                            attr_device_class=SensorDeviceClass.TEMPERATURE,
                            val_fact=0.1,
                            display_precision=1,
                            enabled=ge_ok,
                            dev_info=dev_info,
                        )
                    )
                elif key.find("_humidity") != -1:
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            var_name=key,
                            unique_id=None,
                            var_description="",
                            var_unit=PERCENTAGE,
                            var_type=VarType.FLOAT,
                            attr_entity_category=None,
                            attr_device_class=SensorDeviceClass.HUMIDITY,
                            val_fact=1.0,
                            display_precision=0,
                            enabled=ge_ok,
                            dev_info=dev_info,
                        )
                    )

    if len(res) > 0:
        return res
    return None


def find_weather(
    coordinator: HiqDataUpdateCoordinator,
    add_all: bool = False,
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
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                if key.find("_temperature") != -1:
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            var_name=key,
                            unique_id=None,
                            var_description="",
                            var_unit=UnitOfTemperature.CELSIUS,
                            var_type=VarType.FLOAT,
                            attr_entity_category=None,
                            attr_device_class=SensorDeviceClass.TEMPERATURE,
                            val_fact=0.1,
                            display_precision=1,
                            enabled=ge_ok,
                            dev_info=dev_info,
                        )
                    )
                elif key.find("_humidity") != -1:
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            var_name=key,
                            unique_id=None,
                            var_description="",
                            var_unit=PERCENTAGE,
                            var_type=VarType.FLOAT,
                            attr_entity_category=None,
                            attr_device_class=SensorDeviceClass.HUMIDITY,
                            val_fact=1.0,
                            display_precision=0,
                            enabled=ge_ok,
                            dev_info=dev_info,
                        )
                    )
                elif key.find("_wind_speed") != -1:
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            var_name=key,
                            unique_id=None,
                            attr_device_class=SensorDeviceClass.WIND_SPEED,
                            attr_entity_category=None,
                            val_fact=0.1,
                            var_type=VarType.FLOAT,
                            var_unit=UnitOfSpeed.KILOMETERS_PER_HOUR,
                            display_precision=1,
                            dev_info=dev_info,
                            enabled=ge_ok,
                        )
                    )

    if len(res) > 0:
        return res
    return None


def find_power_meter(
    coordinator: HiqDataUpdateCoordinator,
    add_all: bool = False,
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
                is_ok = _is_power_meter_ok(coordinator, key)
                if is_ok or add_all:
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            var_name=key,
                            unique_id=None,
                            var_description="",
                            var_unit=UnitOfPower.WATT,
                            var_type=VarType.FLOAT,
                            attr_entity_category=None,
                            attr_device_class=SensorDeviceClass.POWER,
                            val_fact=1.0,
                            display_precision=0,
                            enabled=is_ok,
                            dev_info=dev_info,
                        )
                    )
            elif key.find("_voltage") != -1:
                is_ok = _is_power_meter_ok(coordinator, key)
                if is_ok or add_all:
                    fact = 1.0
                    val = coordinator.data.vars.get(key, None)
                    if val is not None and float(val.value.replace(",", "")) > 300:
                        fact = 0.1
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            var_name=key,
                            unique_id=None,
                            var_description="",
                            var_unit=UnitOfElectricPotential.VOLT,
                            var_type=VarType.FLOAT,
                            attr_entity_category=None,
                            attr_device_class=SensorDeviceClass.VOLTAGE,
                            val_fact=fact,
                            display_precision=0,
                            enabled=False,
                            dev_info=dev_info,
                        )
                    )
            elif key.find("_current") != -1:
                is_ok = _is_power_meter_ok(coordinator, key)
                if is_ok or add_all:
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            var_name=key,
                            unique_id=None,
                            var_description="",
                            var_unit=UnitOfElectricCurrent.MILLIAMPERE,
                            var_type=VarType.FLOAT,
                            attr_entity_category=None,
                            attr_device_class=SensorDeviceClass.CURRENT,
                            val_fact=1.0,
                            display_precision=0,
                            enabled=False,
                            dev_info=dev_info,
                        )
                    )
            elif key in (f"{var_prefix}_energy", f"{var_prefix}_energy_real"):
                is_ok = _is_power_meter_ok(coordinator, key)
                if is_ok or add_all:
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            var_name=key,
                            unique_id=None,
                            var_description="",
                            var_unit=UnitOfEnergy.KILO_WATT_HOUR,
                            var_type=VarType.FLOAT,
                            attr_entity_category=None,
                            attr_device_class=SensorDeviceClass.ENERGY,
                            val_fact=1.0,
                            display_precision=0,
                            enabled=is_ok,
                            dev_info=dev_info,
                        )
                    )
            elif key.find(f"{var_prefix}_energy_watthours") != -1:
                is_ok = _is_power_meter_ok(coordinator, key)
                if is_ok or add_all:
                    res.append(
                        HiqSensorEntity(
                            coordinator=coordinator,
                            var_name=key,
                            unique_id=None,
                            var_description="",
                            var_unit=UnitOfEnergy.WATT_HOUR,
                            var_type=VarType.FLOAT,
                            attr_entity_category=None,
                            attr_device_class=SensorDeviceClass.ENERGY,
                            val_fact=1.0,
                            display_precision=0,
                            enabled=False,
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
    add_all: bool = False,
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
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        var_name=f"{unique_id} thermostat temperature",
                        unique_id=key,
                        var_description="",
                        var_unit=UnitOfTemperature.CELSIUS,
                        var_type=VarType.FLOAT,
                        attr_entity_category=None,
                        attr_device_class=SensorDeviceClass.TEMPERATURE,
                        val_fact=0.1,
                        display_precision=1,
                        enabled=ge_ok,
                        dev_info=dev_info,
                    )
                )
        elif key == f"{unique_id}_temperature_1":
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        var_name=f"{unique_id} thermostat temperature 1",
                        unique_id=key,
                        var_description="",
                        var_unit=UnitOfTemperature.CELSIUS,
                        var_type=VarType.FLOAT,
                        attr_entity_category=None,
                        attr_device_class=SensorDeviceClass.TEMPERATURE,
                        val_fact=0.1,
                        display_precision=1,
                        enabled=ge_ok,
                        dev_info=dev_info,
                    )
                )
        # get humidity of thermostat
        elif key == f"{unique_id}_humidity":
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        var_name=f"{unique_id} thermostat humidity",
                        unique_id=key,
                        var_description="",
                        var_unit=PERCENTAGE,
                        var_type=VarType.FLOAT,
                        attr_entity_category=None,
                        attr_device_class=SensorDeviceClass.HUMIDITY,
                        val_fact=1.0,
                        display_precision=0,
                        enabled=ge_ok,
                        dev_info=dev_info,
                    )
                )
        # get light sensor of thermostat
        elif key == f"{unique_id}_light_sensor":
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        var_name=f"{unique_id} thermostat light sensor",
                        unique_id=key,
                        var_description="",
                        var_unit=PERCENTAGE,
                        var_type=VarType.FLOAT,
                        attr_entity_category=None,
                        attr_device_class=None,
                        val_fact=0.097751711,  # sensor is returning 0..1023 = 0..100%
                        display_precision=1,
                        enabled=False,
                        dev_info=dev_info,
                    )
                )
        # get remaining max time
        elif key == f"{unique_id}_max_timer":
            ge_ok = is_general_error_ok(coordinator, key)
            if add_all or ge_ok:
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        var_name=f"{unique_id} thermostat max timer remain",
                        unique_id=key,
                        var_description="",
                        var_unit=UnitOfTime.SECONDS,
                        var_type=VarType.INT,
                        attr_entity_category=None,
                        attr_device_class=SensorDeviceClass.DURATION,
                        val_fact=1.0,
                        display_precision=0,
                        enabled=False,
                        dev_info=dev_info,
                    )
                )

    if len(res) > 0:
        return res
    return None


def add_hvac_tags(
    coordinator: HiqDataUpdateCoordinator,
    add_all: bool = False,
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
            is_ok = _is_enabled(f"c{coordinator.cybro.nad}.outdoor_temperature_enable")
            if add_all or is_ok:
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        var_name=f"{unique_id} HVAC outdoor temperature",
                        unique_id=key,
                        var_description="",
                        var_unit=UnitOfTemperature.CELSIUS,
                        var_type=VarType.FLOAT,
                        attr_entity_category=None,
                        attr_device_class=SensorDeviceClass.TEMPERATURE,
                        val_fact=0.1,
                        display_precision=1,
                        enabled=True,
                        dev_info=dev_info,
                    )
                )
        if key == f"{unique_id}.wall_temperature":
            is_ok = _is_enabled(f"c{coordinator.cybro.nad}.wall_temperature_enable")
            if add_all or is_ok:
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        var_name=f"{unique_id} HVAC wall temperature",
                        unique_id=key,
                        var_description="",
                        var_unit=UnitOfTemperature.CELSIUS,
                        var_type=VarType.FLOAT,
                        attr_entity_category=None,
                        attr_device_class=SensorDeviceClass.TEMPERATURE,
                        val_fact=0.1,
                        display_precision=1,
                        enabled=is_ok,
                        dev_info=dev_info,
                    )
                )
        if key == f"{unique_id}.water_temperature":
            is_ok = _is_enabled(f"c{coordinator.cybro.nad}.water_temperature_enable")
            if add_all or is_ok:
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        var_name=f"{unique_id} HVAC water temperature",
                        unique_id=key,
                        var_description="",
                        var_unit=UnitOfTemperature.CELSIUS,
                        var_type=VarType.FLOAT,
                        attr_entity_category=None,
                        attr_device_class=SensorDeviceClass.TEMPERATURE,
                        val_fact=0.1,
                        display_precision=1,
                        enabled=is_ok,
                        dev_info=dev_info,
                    )
                )
        if key == f"{unique_id}.auxilary_temperature":
            is_ok = _is_enabled(f"c{coordinator.cybro.nad}.auxilary_temperature_enable")
            if add_all or is_ok:
                res.append(
                    HiqSensorEntity(
                        coordinator=coordinator,
                        var_name=f"{unique_id} HVAC auxilary temperature",
                        unique_id=key,
                        var_description="",
                        var_unit=UnitOfTemperature.CELSIUS,
                        var_type=VarType.FLOAT,
                        attr_entity_category=None,
                        attr_device_class=SensorDeviceClass.TEMPERATURE,
                        val_fact=0.1,
                        display_precision=1,
                        enabled=is_ok,
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
        var_name: str = "",
        unique_id: str | None = None,
        var_description: str = "",
        var_unit: str | None = None,
        var_type: VarType = VarType.INT,
        attr_entity_category: EntityCategory = None,
        attr_device_class: SensorDeviceClass = None,
        val_fact: float = 1.0,
        display_precision: int | None = 1,
        enabled: bool = True,
        dev_info: DeviceInfo = None,
    ) -> None:
        """Initialize a HIQ-Home sensor entity."""
        super().__init__(coordinator=coordinator)
        if var_name == "":
            return
        self._attr_native_unit_of_measurement = var_unit
        self._unique_id = var_name
        self._attr_unique_id = unique_id or var_name
        self._attr_name = var_description if var_description != "" else var_name
        self._state = None
        self._attr_device_info = dev_info
        self._attr_entity_category = attr_entity_category
        self._attr_suggested_display_precision = display_precision

        self._attr_device_class = attr_device_class
        if attr_device_class == SensorDeviceClass.ENERGY:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        if enabled is False:
            self._attr_entity_registry_enabled_default = False
        LOGGER.debug(self._attr_unique_id)
        coordinator.data.add_var(self._attr_unique_id, var_type=var_type)
        self._var_type = var_type
        self._val_fact = val_fact

    @property
    def native_value(self) -> datetime | StateType | None:
        """Return the state of the sensor."""
        return self.coordinator.get_value(
            self._attr_unique_id, self._val_fact, self._attr_suggested_display_precision
        )

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
