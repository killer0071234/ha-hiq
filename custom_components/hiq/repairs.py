"""Repair of the A-bus port used by an app (CybroScgiServer, Cybro Edge Toolkit)."""

from __future__ import annotations

import voluptuous as vol
from aiohasupervisor import SupervisorError
from aiohasupervisor.models import AddonBoot
from aiohasupervisor.models import AddonsOptions
from aiohasupervisor.models import AddonState
from aiohasupervisor.models import InstalledAddon
from aiohasupervisor.models import InstalledAddonComplete
from homeassistant.components.repairs import RepairsFlow
from homeassistant.components.repairs import RepairsFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.hassio import is_hassio

from .const import CONF_CONNECTION
from .const import CONNECTION_DIRECT
from .const import CONNECTION_SCGI
from .const import DOMAIN
from .const import ISSUE_PORT_IN_USE
from .const import LOGGER


def _supervisor(hass: HomeAssistant):
    """Return the Supervisor client (hassio is only loaded on supervised systems)."""
    from homeassistant.components.hassio import get_supervisor_client  # noqa: PLC0415

    return get_supervisor_client(hass)


def _uses_port(info: InstalledAddonComplete, port: int) -> bool:
    """Return True if the app declares the UDP port on the host."""
    for container_port, host_port in (info.network or {}).items():
        number, _, protocol = container_port.partition("/")
        # host network: the container ports are the host ports
        if (
            protocol == "udp"
            and (int(number) if info.host_network else host_port) == port
        ):
            return True
    return False


async def async_apps_using_port(hass: HomeAssistant, port: int) -> list[InstalledAddon]:
    """Return the running apps that use the UDP port, if Home Assistant has apps."""
    if not is_hassio(hass):
        return []
    client = _supervisor(hass).addons
    try:
        apps = [app for app in await client.list() if app.state == AddonState.STARTED]
        return [
            app for app in apps if _uses_port(await client.addon_info(app.slug), port)
        ]
    except SupervisorError as err:
        LOGGER.debug("Can't read the apps: %s", err)
        return []


async def async_create_port_issue(
    hass: HomeAssistant, port: int, apps: list[InstalledAddon], reason: str
) -> None:
    """Report that the A-bus port isn't used, fixable if apps hold it."""
    # every socket opened for an entry or flow reports the same
    # (an issue of the last run is loaded inactive)
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_PORT_IN_USE)
    log = LOGGER.debug if issue is not None and issue.active else LOGGER.warning
    log("UDP port %s %s, controllers can't send to Home Assistant", port, reason)
    placeholders = {"port": str(port)}
    if not apps:
        ir.async_create_issue(
            hass,
            DOMAIN,
            ISSUE_PORT_IN_USE,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_PORT_IN_USE,
            translation_placeholders=placeholders,
        )
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_PORT_IN_USE,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=f"{ISSUE_PORT_IN_USE}_app",
        translation_placeholders=placeholders
        | {"app": ", ".join(app.name for app in apps)},
        data={"slugs": ",".join(app.slug for app in apps)},
    )


async def async_reconnect(hass: HomeAssistant) -> None:
    """Open the shared socket again, it binds the A-bus port if it is free."""
    entries = [
        entry
        for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        if entry.options.get(CONF_CONNECTION) == CONNECTION_DIRECT
    ]
    if not entries:
        # no socket open, nothing uses the port
        ir.async_delete_issue(hass, DOMAIN, ISSUE_PORT_IN_USE)
        return
    # the socket is closed with the last entry, a reload would keep it open
    for entry in entries:
        await hass.config_entries.async_unload(entry.entry_id)
    for entry in entries:
        await hass.config_entries.async_setup(entry.entry_id)


class StopAppsFlow(RepairsFlow):
    """Stop the apps, so the direct connection gets the A-bus port."""

    def __init__(self, slugs: list[str]) -> None:
        """Initialize with the app slugs."""
        self._slugs = slugs

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Show what stops working, scgi entries depend on the apps."""
        scgi_entries = [
            entry.title
            for entry in self.hass.config_entries.async_entries(
                DOMAIN, include_ignore=False
            )
            if entry.options.get(CONF_CONNECTION) == CONNECTION_SCGI
        ]
        issue = ir.async_get(self.hass).async_get_issue(DOMAIN, ISSUE_PORT_IN_USE)
        self._placeholders = {"app": issue.translation_placeholders["app"]}
        if scgi_entries:
            self._placeholders["entries"] = ", ".join(scgi_entries)
            return await self.async_step_confirm_scgi()
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Confirm stopping the app."""
        return await self._async_confirm("confirm", user_input)

    async def async_step_confirm_scgi(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Confirm stopping the app, scgi entries stop working."""
        return await self._async_confirm("confirm_scgi", user_input)

    async def _async_confirm(
        self, step_id: str, user_input: dict[str, str] | None
    ) -> RepairsFlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id=step_id,
                data_schema=vol.Schema({}),
                description_placeholders=self._placeholders,
            )
        client = _supervisor(self.hass).addons
        for slug in self._slugs:
            try:
                # else the conflict is back after the next reboot
                await client.set_addon_options(
                    slug, AddonsOptions(boot=AddonBoot.MANUAL)
                )
                await client.stop_addon(slug)
            except SupervisorError as err:
                LOGGER.error("Can't stop the app %s: %s", slug, err)
                return self.async_abort(reason="stop_failed")
        await async_reconnect(self.hass)
        if ir.async_get(self.hass).async_get_issue(DOMAIN, ISSUE_PORT_IN_USE):
            return self.async_abort(reason="still_in_use")
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the flow that fixes an issue."""
    return StopAppsFlow(str(data["slugs"]).split(","))
