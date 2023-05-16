"""Support for HIQ-Home."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
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
    address = entry.data[CONF_ADDRESS]
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when its updated.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Add service handler(s)
    async def handle_presence_signal(call: ServiceCall) -> None:
        """Handle service call for smartphone presence signal."""
        LOGGER.debug(
            "Call %s with tag c%s.smartphone_presence_signal",
            SERVICE_PRESENCE_SIGNAL,
            address,
        )
        await coordinator.cybro.write_var(f"c{address}.smartphone_presence_signal", "1")

    async def handle_charge_on_event(call: ServiceCall) -> None:
        """Handle service call for smartphone charge on event."""
        LOGGER.debug(
            "Call %s with tag c%s.smartphone_charge_on_event",
            SERVICE_CHARGE_ON,
            address,
        )
        await coordinator.cybro.write_var(f"c{address}.smartphone_charge_on_event", "1")

    async def handle_charge_off_event(call: ServiceCall) -> None:
        """Handle service call for smartphone charge off event."""
        LOGGER.debug(
            "Call %s with tag c%s.smartphone_charge_off_event",
            SERVICE_CHARGE_OFF,
            address,
        )
        await coordinator.cybro.write_var(
            f"c{address}.smartphone_charge_off_event", "1"
        )

    async def handle_home_event(call: ServiceCall) -> None:
        """Handle service call for smartphone home event."""
        LOGGER.debug(
            "Call %s with tag c%s.smartphone_home_event", SERVICE_HOME, address
        )
        await coordinator.cybro.write_var(f"c{address}.smartphone_home_event", "1")

    async def handle_alarm_event(call: ServiceCall) -> None:
        """Handle service call for smartphone alarm event."""
        LOGGER.debug(
            "Call %s with tag c%s.smartphone_alarm_event", SERVICE_ALARM, address
        )
        await coordinator.cybro.write_var(f"c{address}.smartphone_alarm_event", "1")

    async def handle_precede_event(call: ServiceCall) -> None:
        """Handle service call for smartphone precede event."""
        LOGGER.debug(
            "Call %s with tag c%s.smartphone_precede_event and c%s.smartphone_precede_minutes",
            SERVICE_PRECEDE,
            address,
            call.data["time"],
        )
        await coordinator.cybro.write_var(
            f"c{address}.smartphone_precede_minutes", call.data["time"]
        )
        await coordinator.cybro.write_var(f"c{address}.smartphone_precede_event", "1")

    async def handle_write_tag(call: ServiceCall) -> None:
        """Handle service call to write a single tag in controller."""
        LOGGER.debug(
            "Call %s with tag c%s.%s and value = %s",
            SERVICE_WRITE_TAG,
            address,
            call.data["tag"],
            call.data["value"],
        )
        await coordinator.cybro.write_var(
            f"c{address}.{call.data['tag']}", call.data["value"]
        )
        await coordinator.cybro.write_var(f"c{address}.smartphone_precede_event", "1")

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
