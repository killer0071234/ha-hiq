"""Support for HIQ-Home sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from re import search
from re import sub
from typing import Any

import voluptuous as vol
from cybro import VarType
from homeassistant.components.sensor import CONF_STATE_CLASS
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.sensor import SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.const import PERCENTAGE
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.const import UnitOfElectricPotential
from homeassistant.const import UnitOfEnergy
from homeassistant.const import UnitOfFrequency
from homeassistant.const import UnitOfPower
from homeassistant.const import UnitOfTemperature
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.trigger_template_entity import (
    TEMPLATE_SENSOR_BASE_SCHEMA,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.typing import StateType

from .const import AREA_ENERGY
from .const import AREA_SYSTEM
from .const import AREA_WEATHER
from .const import ATTR_DESCRIPTION
from .const import ATTR_VARIABLE
from .const import CONF_TAG
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
from .models import thermostat_device_info
from .models import hvac_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HIQ-Home sensor based on a config entry."""
    coordinator: HiqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    for find_sensors in (
        add_system_tags,
        find_temperatures,
        find_power_meter,
        add_th_tags,
        add_hvac_tags,
    ):
        if (sensors := find_sensors(coordinator)) is not None:
            async_add_entities(sensors)

    # add custom defined sensors
    custom_entities: list = []
    config = dict(entry.options)
    if config.get("sensor") is None:
        return
    var_prefix = f"c{coordinator.cybro.nad}."
    dev_info = DeviceInfo(
        identifiers={(DOMAIN, f"{coordinator.data.plc_info.nad} custom")},
        manufacturer=MANUFACTURER,
        name=f"c{coordinator.cybro.nad} custom",
        # suggested_area=AREA_SYSTEM,
        model=DEVICE_DESCRIPTION,
        configuration_url=MANUFACTURER_URL,
        entry_type=None,
        sw_version=DEVICE_SW_VERSION,
        hw_version=DEVICE_HW_VERSION,
    )
    for sensor in config["sensor"]:
        sensor_config: ConfigType = vol.Schema(
            TEMPLATE_SENSOR_BASE_SCHEMA.schema, extra=vol.ALLOW_EXTRA
        )(sensor)

        name_string: Template = sensor_config.get(CONF_NAME)

        value_string: str | None = sensor_config.get(CONF_VALUE_TEMPLATE)

        value_template: Template | None = (
            Template(value_string, hass) if value_string is not None else None
        )
        var = f"{var_prefix}{sensor_config.get(CONF_TAG)}"
        unique_id = sensor_config.get(CONF_UNIQUE_ID) or var
        if unique_id != var:
            _migrate_custom_sensor_unique_id(hass, dev_info, var, unique_id)
        custom_entities.append(
            HiqSensorEntity(
                coordinator=coordinator,
                unique_id=unique_id,
                entity_description=HiqSensorEntityDescription(
                    key=var,
                    name=name_string.template,
                    state_class=SensorStateClass(sensor_config[CONF_STATE_CLASS])
                    if sensor_config.get(CONF_STATE_CLASS) is not None
                    else None,
                    device_class=SensorDeviceClass(sensor_config[CONF_DEVICE_CLASS])
                    if sensor_config.get(CONF_DEVICE_CLASS) is not None
                    else None,
                    native_unit_of_measurement=sensor_config.get(
                        CONF_UNIT_OF_MEASUREMENT
                    ),
                ),
                dev_info=dev_info,
                value_template=value_template,
            )
        )

    async_add_entities(custom_entities)


def _migrate_custom_sensor_unique_id(
    hass: HomeAssistant, dev_info: DeviceInfo, old_unique_id: str, unique_id: str
) -> None:
    """Move a custom sensor from the tag name to its own unique id.

    Custom sensors used the tag name as unique id before, which collides with
    built-in sensors of the same tag, so only entities of the custom device move.
    """
    entity_registry = er.async_get(hass)
    if entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id):
        return
    if not (
        entity_id := entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, old_unique_id
        )
    ):
        return
    entity = entity_registry.async_get(entity_id)
    device = dr.async_get(hass).async_get(entity.device_id or "")
    if device is None or not device.identifiers & dev_info["identifiers"]:
        return
    LOGGER.debug("Migrate unique id of %s to %s", entity_id, unique_id)
    entity_registry.async_update_entity(entity_id, new_unique_id=unique_id)


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
        if var_prefix not in key:
            continue
        val_fact = 1.0
        var_type = VarType.INT
        if key in (f"{var_prefix}scan_time", f"{var_prefix}scan_time_max"):
            description = {
                "native_unit_of_measurement": UnitOfTime.MILLISECONDS,
                "entity_registry_enabled_default": False,
                "suggested_display_precision": 0,
            }
        elif key in (f"{var_prefix}cybro_uptime", f"{var_prefix}operating_hours"):
            description = {
                "native_unit_of_measurement": UnitOfTime.HOURS,
                "device_class": SensorDeviceClass.DURATION,
                "suggested_display_precision": 0,
            }
        elif key in (f"{var_prefix}scan_frequency"):
            description = {
                "native_unit_of_measurement": UnitOfFrequency.HERTZ,
                "entity_registry_enabled_default": False,
                "suggested_display_precision": 0,
            }
        elif "iex_power_supply" in key or "cybro_power_supply" in key:
            module_name = key.removeprefix(var_prefix).split("_")[0]
            translation_key = "iex_power_supply_iex"
            translation_placeholders = {"module": module_name}
            if module_name in ("iex", "cybro"):
                translation_key = f"{module_name}_power_supply"
                translation_placeholders = None
            description = {
                "translation_key": translation_key,
                "translation_placeholders": translation_placeholders,
                "native_unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "entity_registry_enabled_default": False,
                "suggested_display_precision": 1,
            }
            var_type = VarType.FLOAT
            val_fact = 0.1
        else:
            continue
        res.append(
            HiqSensorEntity(
                coordinator=coordinator,
                entity_description=HiqSensorEntityDescription(
                    key=key,
                    state_class=SensorStateClass.MEASUREMENT,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    **description,
                ),
                var_type=var_type,
                val_fact=val_fact,
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
        **coordinator.via_device_info,
    )

    for key in coordinator.data.plc_info.plc_vars:
        if not (".op" in key or ".ts" in key or ".fc" in key):
            continue
        if not is_general_error_ok(coordinator, key):
            continue
        if "_temperature" in key:
            description = {
                "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
                "device_class": SensorDeviceClass.TEMPERATURE,
                "suggested_display_precision": 1,
            }
            val_fact = 0.1
        elif "_humidity" in key:
            description = {
                "native_unit_of_measurement": PERCENTAGE,
                "device_class": SensorDeviceClass.HUMIDITY,
                "suggested_display_precision": 0,
            }
            val_fact = 1.0
        else:
            continue
        res.append(
            HiqSensorEntity(
                coordinator=coordinator,
                entity_description=HiqSensorEntityDescription(
                    key=key,
                    **_module_sensor_name(coordinator, key),
                    state_class=SensorStateClass.MEASUREMENT,
                    **description,
                ),
                var_type=VarType.FLOAT,
                val_fact=val_fact,
                dev_info=dev_info,
            )
        )

    if len(res) > 0:
        return res
    return None


def _module_sensor_name(
    coordinator: HiqDataUpdateCoordinator, var: str
) -> dict[str, Any]:
    """Return the name of a temperature module sensor, eg: ts00 internal temperature."""
    module_name, _, measurement = var.removeprefix(
        f"c{coordinator.cybro.nad}."
    ).partition("_")
    translation_key = {
        "temperature_0": "module_temperature_internal",
        "temperature_1": "module_temperature_external",
        "humidity": "module_humidity",
    }.get(measurement, "module_temperature")
    return {
        "translation_key": translation_key,
        "translation_placeholders": {"module": module_name},
    }


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
        **coordinator.via_device_info,
    )
    for key in coordinator.data.plc_info.plc_vars:
        if var_prefix not in key:
            continue
        if "_power" in key:
            description = {
                **_power_meter_phase_name(key),
                "native_unit_of_measurement": UnitOfPower.WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "suggested_display_precision": 0,
            }
        elif "_voltage" in key:
            description = {
                **_power_meter_phase_name(key),
                "native_unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
                "entity_registry_enabled_default": False,
                "suggested_display_precision": 0,
            }
        elif "_current" in key:
            description = {
                **_power_meter_phase_name(key),
                "native_unit_of_measurement": UnitOfElectricCurrent.MILLIAMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
                "entity_registry_enabled_default": False,
                "suggested_display_precision": 0,
            }
        elif key == f"{var_prefix}_energy":
            description = {
                "native_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
                "suggested_display_precision": 0,
            }
        elif key == f"{var_prefix}_energy_real":
            description = {
                "native_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
                "entity_registry_enabled_default": False,
                "suggested_display_precision": 3,
            }
        elif f"{var_prefix}_energy_watthours" in key:
            description = {
                "native_unit_of_measurement": UnitOfEnergy.WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
                "entity_registry_enabled_default": False,
                "suggested_display_precision": 0,
            }
        else:
            continue
        if not _is_power_meter_ok(coordinator, key):
            continue
        val_fact = 1.0
        if description["device_class"] == SensorDeviceClass.VOLTAGE:
            val_fact = _power_meter_voltage_factor(coordinator, key)
        res.append(
            HiqSensorEntity(
                coordinator=coordinator,
                entity_description=HiqSensorEntityDescription(
                    key=key,
                    **description,
                ),
                var_type=VarType.FLOAT,
                val_fact=val_fact,
                dev_info=dev_info,
            )
        )

    if len(res) > 0:
        return res
    return None


def _power_meter_phase_name(var: str) -> dict[str, Any]:
    """Return the name of a single phase sensor of the power meter, eg: Power L1."""
    phase = search(r"_(power|voltage|current)(\d)$", var)
    if phase is None:
        return {}
    return {
        "translation_key": f"power_meter_{phase.group(1)}_phase",
        "translation_placeholders": {"phase": phase.group(2)},
    }


def _power_meter_voltage_factor(
    coordinator: HiqDataUpdateCoordinator, var: str
) -> float:
    """Return the factor of a voltage, some meters report it in 0.1 V."""
    val = coordinator.data.vars.get(var)
    if (
        val is not None
        and val.value not in (None, "?")
        and float(val.value.replace(",", "")) > 300
    ):
        return 0.1
    return 1.0


def _is_power_meter_ok(coordinator: HiqDataUpdateCoordinator, var: str):
    ge_name = f"{var.split('_')[0]}_meter_error"
    coordinator.data.add_var(ge_name)
    ge_val = coordinator.data.vars.get(ge_name)
    if ge_val is None:
        return False
    LOGGER.debug("%s -> %s", ge_name, ge_val.value)
    return ge_val.value == "0"


# thermostat sensors: name -> (description fields, var type, value factor)
TH_SENSORS: dict[str, tuple[dict[str, Any], VarType, float]] = {
    "temperature": (
        {
            "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
            "device_class": SensorDeviceClass.TEMPERATURE,
            "state_class": SensorStateClass.MEASUREMENT,
            "suggested_display_precision": 1,
        },
        VarType.FLOAT,
        0.1,
    ),
    "temperature_1": (
        {
            "translation_key": "temperature_1",
            "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
            "device_class": SensorDeviceClass.TEMPERATURE,
            "state_class": SensorStateClass.MEASUREMENT,
            "suggested_display_precision": 1,
        },
        VarType.FLOAT,
        0.1,
    ),
    "humidity": (
        {
            "native_unit_of_measurement": PERCENTAGE,
            "device_class": SensorDeviceClass.HUMIDITY,
            "state_class": SensorStateClass.MEASUREMENT,
            "suggested_display_precision": 0,
        },
        VarType.FLOAT,
        1.0,
    ),
    "light_sensor": (
        {
            "translation_key": "light_sensor",
            "native_unit_of_measurement": PERCENTAGE,
            "state_class": SensorStateClass.MEASUREMENT,
            "entity_registry_enabled_default": False,
            "suggested_display_precision": 1,
        },
        VarType.FLOAT,
        0.097751711,  # sensor is returning 0..1023 = 0..100%
    ),
    "max_timer": (
        {
            "translation_key": "max_timer_remain",
            "native_unit_of_measurement": UnitOfTime.SECONDS,
            "device_class": SensorDeviceClass.DURATION,
            "state_class": SensorStateClass.MEASUREMENT,
            "entity_registry_enabled_default": False,
            "suggested_display_precision": 0,
        },
        VarType.INT,
        1.0,
    ),
}


def add_th_tags(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqSensorEntity] | None:
    """Find temperature sensors for thermostat tags in the plc vars.
    eg: c1000.th00_floor_tmp and so on.
    """
    res: list[HiqSensorEntity] = []

    # find different thermostat vars
    for key in coordinator.data.plc_info.plc_vars:
        # identifier is cNAD.thNR
        grp = search(r"c\d+\.th\d+", key)
        if not grp or not key.startswith(f"{grp.group()}_"):
            continue
        unique_id = grp.group()
        name = key.removeprefix(f"{unique_id}_")
        if name not in TH_SENSORS or not is_general_error_ok(coordinator, key):
            continue
        description, var_type, val_fact = TH_SENSORS[name]
        res.append(
            HiqSensorEntity(
                coordinator=coordinator,
                entity_description=HiqSensorEntityDescription(key=key, **description),
                var_type=var_type,
                val_fact=val_fact,
                dev_info=thermostat_device_info(coordinator, unique_id),
            )
        )

    if len(res) > 0:
        return res
    return None


HVAC_TEMPERATURES = (
    "outdoor_temperature",
    "wall_temperature",
    "water_temperature",
    "auxilary_temperature",
)


def add_hvac_tags(
    coordinator: HiqDataUpdateCoordinator,
) -> list[HiqSensorEntity] | None:
    """Find and add HVAC tags in the plc vars.
    eg: c1000.outdoor_temperature and so on.
    """
    res: list[HiqSensorEntity] = []

    def _is_enabled(tag: str) -> bool:
        """Get enable state of variable."""
        value = coordinator.data.vars.get(tag)
        if value is None:
            return False
        LOGGER.debug("%s -> %s", tag, value.value)
        return value.value == "1"

    # find different hvac related vars
    for key in coordinator.data.plc_info.plc_vars:
        # identifier is cNAD
        grp = search(r"c\d+", key)
        if not grp or not key.startswith(f"{grp.group()}."):
            continue
        unique_id = grp.group()
        name = key.removeprefix(f"{unique_id}.")
        if name not in HVAC_TEMPERATURES:
            continue
        res.append(
            HiqSensorEntity(
                coordinator=coordinator,
                entity_description=HiqSensorEntityDescription(
                    key=key,
                    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                    device_class=SensorDeviceClass.TEMPERATURE,
                    state_class=SensorStateClass.MEASUREMENT,
                    entity_registry_enabled_default=_is_enabled(
                        f"c{coordinator.cybro.nad}.{name}_enable"
                    ),
                    suggested_display_precision=1,
                ),
                var_type=VarType.FLOAT,
                val_fact=0.1,
                dev_info=hvac_device_info(coordinator, unique_id),
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
        value_template: Template | None = None,
    ) -> None:
        """Initialize a HIQ-Home sensor entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = unique_id or entity_description.key
        self._attr_device_info = dev_info
        self._var = entity_description.key
        LOGGER.debug(self._attr_unique_id)
        # set var type to string for template handling (conversion shall be done in template)
        self._var_type = var_type if value_template is None else VarType.STR
        coordinator.data.add_var(self._var, var_type=self._var_type)
        self._val_fact = val_fact
        self._value_template = value_template

    @property
    def native_value(self) -> datetime | StateType | None:
        """Return the state of the sensor."""

        if self._value_template is not None:
            return self.coordinator.get_template_value(self._var, self._value_template)

        return self.coordinator.get_value(
            self._var, self._val_fact, self.suggested_display_precision
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        try:
            desc = self.coordinator.data.vars[self._var].description
        except KeyError:
            desc = "?"
        return {
            ATTR_DESCRIPTION: desc,
            ATTR_VARIABLE: self._var,
        }
