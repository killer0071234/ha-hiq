"""Support for HIQ-Home."""

from __future__ import annotations

from re import search

import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
import voluptuous as vol
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.const import CONF_ADDRESS
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_PORT
from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.trigger_template_entity import (
    TEMPLATE_SENSOR_BASE_SCHEMA,
)

from .const import AREA_SYSTEM
from .const import CONF_TAG
from .const import DEFAULT_HOST
from .const import DEFAULT_PORT
from .const import DEVICE_DESCRIPTION
from .const import DEVICE_HW_VERSION
from .const import DEVICE_SW_VERSION
from .const import DOMAIN
from .const import LOGGER
from .const import MANUFACTURER
from .const import MANUFACTURER_URL
from .const import SERVICE_ALARM
from .const import SERVICE_CHARGE_OFF
from .const import SERVICE_CHARGE_ON
from .const import SERVICE_HOME
from .const import SERVICE_PRECEDE
from .const import SERVICE_PRESENCE_SIGNAL
from .const import SERVICE_WRITE_TAG
from .coordinator import HiqDataUpdateCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.WEATHER,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]

PLC_SCHEMA = {
    vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(CONF_ADDRESS, default=1000): cv.positive_int,
}

SENSOR_SCHEMA = vol.Schema(
    {
        **TEMPLATE_SENSOR_BASE_SCHEMA.schema,
        vol.Required(CONF_TAG): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
)

COMBINED_SCHEMA = vol.Schema(
    {
        **PLC_SCHEMA,
        vol.Optional(SENSOR_DOMAIN): vol.All(
            cv.ensure_list, [vol.Schema(SENSOR_SCHEMA)]
        ),
        vol.Optional(BINARY_SENSOR_DOMAIN): vol.All(
            cv.ensure_list, [vol.Schema(SENSOR_SCHEMA)]
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): vol.All(cv.ensure_list, [COMBINED_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_PRECEDE_SCHEMA = SERVICE_SCHEMA.extend(
    {vol.Required("time"): vol.All(vol.Coerce(int), vol.Range(min=1, max=3600))}
)

SERVICE_WRITE_TAG_SCHEMA = SERVICE_SCHEMA.extend(
    {vol.Required("tag"): cv.string, vol.Required("value"): cv.string}
)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""
    version = entry.version

    LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: move connection parameter from data to options
    if version == 1:
        version = 2

        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]
        nad = entry.data[CONF_ADDRESS]
        title = f"c{nad}@{host}:{port}"
        hass.config_entries.async_update_entry(
            entry,
            unique_id=title,
            title=title,
            data={},
            options={
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_ADDRESS: nad,
            },
            version=version,
        )

    LOGGER.info("Migration to version %s successful", version)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HIQ from a config entry."""
    coordinator = HiqDataUpdateCoordinator(hass, entry=entry)

    await coordinator.async_config_entry_first_refresh()

    # Entities are only created for working modules (and the power meter voltage
    # scale and rgb lights depend on their values), so read these before the
    # platforms are set up
    for var in coordinator.data.plc_info.plc_vars:
        if search(
            r"(_general_error|_meter_error|power_meter_voltage\d*|_rgb_mode(_2)?)$",
            var,
        ):
            coordinator.data.add_var(var)
    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady(
            f"Could not read module states from {coordinator.unique_id}"
        )

    # Register the controller first, so other devices can reference it
    controller = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, coordinator.cybro.nad)},
        manufacturer=MANUFACTURER,
        name=f"c{coordinator.cybro.nad} diagnostic",
        suggested_area=AREA_SYSTEM,
        model=DEVICE_DESCRIPTION,
        configuration_url=MANUFACTURER_URL,
        sw_version=DEVICE_SW_VERSION,
        hw_version=DEVICE_HW_VERSION,
    )
    coordinator.device_id = controller.id

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when its updated.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Add service handler(s)
    async def handle_presence_signal(call: ServiceCall) -> None:
        """Handle service call for smartphone presence signal."""
        write_tags = _get_tag_list(hass, call.data, "smartphone_presence_signal")
        for write_tag in write_tags:
            LOGGER.debug("Write tag '%s' to '1'", write_tag)
            await coordinator.cybro.write_var(write_tag, "1")

    async def handle_charge_on_event(call: ServiceCall) -> None:
        """Handle service call for smartphone charge on event."""
        write_tags = _get_tag_list(hass, call.data, "smartphone_charge_on_event")
        for write_tag in write_tags:
            LOGGER.debug("Write tag '%s' to '1'", write_tag)
            await coordinator.cybro.write_var(write_tag, "1")

    async def handle_charge_off_event(call: ServiceCall) -> None:
        """Handle service call for smartphone charge off event."""
        write_tags = _get_tag_list(hass, call.data, "smartphone_charge_off_event")
        for write_tag in write_tags:
            LOGGER.debug("Write tag '%s' to '1'", write_tag)
            await coordinator.cybro.write_var(write_tag, "1")

    async def handle_home_event(call: ServiceCall) -> None:
        """Handle service call for smartphone home event."""
        write_tags = _get_tag_list(hass, call.data, "smartphone_home_event")
        for write_tag in write_tags:
            LOGGER.debug("Write tag '%s' to '1'", write_tag)
            await coordinator.cybro.write_var(write_tag, "1")

    async def handle_alarm_event(call: ServiceCall) -> None:
        """Handle service call for smartphone alarm event."""
        write_tags = _get_tag_list(hass, call.data, "smartphone_alarm_event")
        for write_tag in write_tags:
            LOGGER.debug("Write tag '%s' to '1'", write_tag)
            await coordinator.cybro.write_var(write_tag, "1")

    async def handle_precede_event(call: ServiceCall) -> None:
        """Handle service call for smartphone precede event."""
        # first of all we write the configured minutes
        write_tags = _get_tag_list(hass, call.data, "smartphone_precede_minutes")
        for write_tag in write_tags:
            LOGGER.debug("Write tag '%s' to '%s'", write_tag, call.data["time"])
            await coordinator.cybro.write_var(write_tag, call.data["time"])
        # and now the event trigger itself
        write_tags = _get_tag_list(hass, call.data, "smartphone_precede_event")
        for write_tag in write_tags:
            LOGGER.debug("Write tag '%s' to '%s'", write_tag, "1")
            await coordinator.cybro.write_var(write_tag, "1")

    async def handle_write_tag(call: ServiceCall) -> None:
        """Handle service call to write a single tag in (one or more) controller(s)."""
        write_tags = _get_tag_list(hass, call.data, call.data["tag"])
        for write_tag in write_tags:
            LOGGER.debug("Write tag '%s' to '%s'", write_tag, call.data["value"])
            await coordinator.cybro.write_var(write_tag, call.data["value"])

    for service, handler, schema in (
        (SERVICE_PRESENCE_SIGNAL, handle_presence_signal, SERVICE_SCHEMA),
        (SERVICE_CHARGE_ON, handle_charge_on_event, SERVICE_SCHEMA),
        (SERVICE_CHARGE_OFF, handle_charge_off_event, SERVICE_SCHEMA),
        (SERVICE_HOME, handle_home_event, SERVICE_SCHEMA),
        (SERVICE_ALARM, handle_alarm_event, SERVICE_SCHEMA),
        (SERVICE_PRECEDE, handle_precede_event, SERVICE_PRECEDE_SCHEMA),
        (SERVICE_WRITE_TAG, handle_write_tag, SERVICE_WRITE_TAG_SCHEMA),
    ):
        hass.services.async_register(DOMAIN, service, handler, schema=schema)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload HIQ config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: HiqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

        # Ensure disconnected and cleanup stop sub
        if coordinator.unsub:
            coordinator.unsub()

        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_PRESENCE_SIGNAL)
            hass.services.async_remove(DOMAIN, SERVICE_CHARGE_ON)
            hass.services.async_remove(DOMAIN, SERVICE_CHARGE_OFF)
            hass.services.async_remove(DOMAIN, SERVICE_HOME)
            hass.services.async_remove(DOMAIN, SERVICE_ALARM)
            hass.services.async_remove(DOMAIN, SERVICE_PRECEDE)
            hass.services.async_remove(DOMAIN, SERVICE_WRITE_TAG)
            del hass.data[DOMAIN]

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(entry.entry_id)


def _get_tag_list(hass: HomeAssistant, data: dict, tag_name: str) -> list:
    """Generate a tag list for write to the controller."""
    # read all possible adresses from HA
    addresses = [
        f"c{entity_id.options[CONF_ADDRESS]}"
        for entity_id in hass.config_entries.async_entries(DOMAIN)
    ]
    target_entities = []

    if entity_ids := data.get(ATTR_ENTITY_ID):
        for entity_id in entity_ids:
            for address in addresses:
                if address in entity_id:
                    target_entities += [f"{address}.{tag_name}"]

    if device_ids := data.get(ATTR_DEVICE_ID):
        registry = dr.async_get(hass)
        for target in device_ids:
            device = registry.async_get(target)
            if device:
                for key in device.config_entries:
                    entry = hass.config_entries.async_get_entry(key)
                    if not entry:
                        continue
                    if entry.domain != DOMAIN:
                        continue
                    if addr := entry.options.get(CONF_ADDRESS):
                        target_entities += [f"c{addr}.{tag_name}"]
                        LOGGER.debug("addr = %s", addr)

    if target_entities:
        return list(dict.fromkeys(target_entities))
    return []


def get_write_req_th(key: str, unique_id: str) -> str | None:
    """Return write req tag for THs or None."""
    if key in (
        f"{unique_id}_temperature_source",
        f"{unique_id}_temperature_offset",
        f"{unique_id}_fan_options",
        f"{unique_id}_display_mode",
    ):
        return f"{unique_id}_config1_req"
    if key in (
        f"{unique_id}_setpoint_idle",
        f"{unique_id}_setpoint_lo",
        f"{unique_id}_setpoint_hi",
        f"{unique_id}_max_time",
    ):
        return f"{unique_id}_config2_req"
    if key in (
        f"{unique_id}_lightness_day",
        f"{unique_id}_lightness_night",
        f"{unique_id}_window_enable",
        f"{unique_id}_beep_enable",
    ):
        return f"{unique_id}_config3_req"
    if key in (f"{unique_id}_dndmmr_enable",):
        return f"{unique_id}_config4_req"
    return None
