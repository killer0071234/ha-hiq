"""Support for HIQ-Home."""
from __future__ import annotations

import homeassistant.helpers.device_registry as dr
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    DOMAIN,
    LOGGER,
    SERVICE_ALARM,
    SERVICE_CHARGE_OFF,
    SERVICE_CHARGE_ON,
    SERVICE_HOME,
    SERVICE_PRECEDE,
    SERVICE_PRESENCE_SIGNAL,
    SERVICE_WRITE_TAG,
)
from .coordinator import HiqDataUpdateCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.WEATHER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HIQ from a config entry."""
    coordinator = HiqDataUpdateCoordinator(hass, entry=entry)

    await coordinator.async_config_entry_first_refresh()

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

    hass.services.async_register(
        DOMAIN, SERVICE_PRESENCE_SIGNAL, handle_presence_signal
    )
    hass.services.async_register(DOMAIN, SERVICE_CHARGE_ON, handle_charge_on_event)
    hass.services.async_register(DOMAIN, SERVICE_CHARGE_OFF, handle_charge_off_event)
    hass.services.async_register(DOMAIN, SERVICE_HOME, handle_home_event)
    hass.services.async_register(DOMAIN, SERVICE_ALARM, handle_alarm_event)
    hass.services.async_register(DOMAIN, SERVICE_PRECEDE, handle_precede_event)
    hass.services.async_register(DOMAIN, SERVICE_WRITE_TAG, handle_write_tag)

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
        f"c{entity_id.data[CONF_ADDRESS]}"
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
                    if addr := entry.data.get(CONF_ADDRESS):
                        target_entities += [f"c{addr}.{tag_name}"]
                        LOGGER.debug("addr = %s", addr)

    if target_entities:
        return list(dict.fromkeys(target_entities))
    return []
