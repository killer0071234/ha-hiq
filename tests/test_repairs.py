"""Tests for the repair of a busy A-bus port (scgi server app)."""

from __future__ import annotations

import logging
from dataclasses import replace
import socket
from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohasupervisor import SupervisorError
from aiohasupervisor.models import AddonBoot, AddonsOptions, AddonState
from cybro.testing import FakeAbusController
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hiq import transport
from custom_components.hiq.const import DOMAIN, ISSUE_PORT_IN_USE
from custom_components.hiq.discovery import async_discover
from custom_components.hiq.transport import async_current_transport

from .fake_abus import TRANSPORT, direct_entry, start_hiq_controller

APP_SLUG = "0fb96a21_cybroscgiserver"
TOOLKIT_SLUG = "0fb96a21_cybroedgetoolkit"


@pytest.fixture
def busy_port() -> Generator[socket.socket]:
    """Return a socket holding a UDP port, the A-bus port of the tests."""
    busy = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    busy.bind(("127.0.0.1", 0))
    with patch(f"{TRANSPORT}.LOCAL_PORT", busy.getsockname()[1]):
        yield busy
    busy.close()


def abus_network(port: int) -> dict[str, int | None]:
    """Return the ports the Cybro apps declare."""
    return {"4000/tcp": 4000, f"{port}/udp": port}


def _app(
    slug: str,
    name: str,
    network: Callable[[int], dict[str, int | None]] | None = abus_network,
    host_network: bool = True,
) -> MagicMock:
    """Return a running app; network gets the A-bus port of the test."""
    app = MagicMock(slug=slug, state=AddonState.STARTED)
    app.name = name
    app.declared = (network, host_network)
    return app


@pytest.fixture
def supervisor(busy_port: socket.socket) -> Generator[MagicMock]:
    """Return the Supervisor client, the scgi server app is running."""
    app = _app(APP_SLUG, "CybroScgiServer")
    client = MagicMock()
    client.app = app
    client.addons.list = AsyncMock(
        return_value=[_app("core_ssh", "Terminal & SSH", lambda _: {"22/tcp": 22}), app]
    )

    async def addon_info(slug: str) -> MagicMock:
        network, host_network = next(
            a.declared for a in client.addons.list.return_value if a.slug == slug
        )
        return MagicMock(
            host_network=host_network,
            network=network(transport.LOCAL_PORT) if network else None,
        )

    client.addons.addon_info = AsyncMock(side_effect=addon_info)

    def stop(slug: str) -> None:
        # stopping the apps frees the port
        for running in client.addons.list.return_value:
            if running.slug == slug:
                running.state = AddonState.STOPPED
        busy_port.close()

    client.addons.stop_addon = AsyncMock(side_effect=stop)
    client.addons.set_addon_options = AsyncMock()
    with (
        patch("custom_components.hiq.repairs.is_hassio", return_value=True),
        patch(
            "homeassistant.components.hassio.get_supervisor_client",
            return_value=client,
        ),
    ):
        yield client


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _start_fix_flow(hass: HomeAssistant) -> dict:
    assert await async_setup_component(hass, "repairs", {})
    return await hass.data["repairs"]["flow_manager"].async_init(
        DOMAIN, data={"issue_id": ISSUE_PORT_IN_USE}
    )


async def _confirm(hass: HomeAssistant, result: dict) -> dict:
    result = await hass.data["repairs"]["flow_manager"].async_configure(
        result["flow_id"], {}
    )
    await hass.async_block_till_done()
    return result


async def test_warning_logged_once(
    hass: HomeAssistant,
    abus_controller: FakeAbusController,
    busy_port: socket.socket,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the busy port is logged once, not for every socket opened."""
    second_controller = await start_hiq_controller(
        1001, host="127.0.0.2", port=abus_controller.port
    )
    with caplog.at_level(logging.DEBUG):
        await _setup(hass, direct_entry())
        await hass.config_entries.async_reload(
            hass.config_entries.async_entries(DOMAIN)[0].entry_id
        )
        await _setup(hass, direct_entry(1001, ip_address="127.0.0.2"))
    second_controller.close()

    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "is in use" in r.getMessage()
    ]
    assert len(warnings) == 1


async def test_issue_not_fixable_without_app(
    hass: HomeAssistant, abus_controller: FakeAbusController, busy_port: socket.socket
) -> None:
    """Test the issue only explains the conflict when no scgi app runs."""
    await _setup(hass, direct_entry())

    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_PORT_IN_USE)
    assert issue.translation_key == "port_in_use"
    assert not issue.is_fixable


async def test_issue_fixable_with_app(
    hass: HomeAssistant, abus_controller: FakeAbusController, supervisor: MagicMock
) -> None:
    """Test the issue names the running scgi server app and can fix it."""
    await _setup(hass, direct_entry())

    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_PORT_IN_USE)
    assert issue.translation_key == "port_in_use_app"
    assert issue.is_fixable
    assert issue.data == {"slugs": APP_SLUG}
    assert issue.translation_placeholders["app"] == "CybroScgiServer"


async def test_fix_stops_app_and_reconnects(
    hass: HomeAssistant, abus_controller: FakeAbusController, supervisor: MagicMock
) -> None:
    """Test the fix stops the app, turns off its start on boot and binds the port."""
    entry = direct_entry()
    await _setup(hass, entry)
    fallback = async_current_transport(hass)

    result = await _start_fix_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"app": "CybroScgiServer"}

    result = await _confirm(hass, result)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    supervisor.addons.set_addon_options.assert_awaited_once_with(
        APP_SLUG, AddonsOptions(boot=AddonBoot.MANUAL)
    )
    supervisor.addons.stop_addon.assert_awaited_once_with(APP_SLUG)
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_PORT_IN_USE) is None
    assert entry.state is ConfigEntryState.LOADED
    assert async_current_transport(hass) is not fallback
    assert async_current_transport(hass).local_addr[1] == transport.LOCAL_PORT
    assert hass.data[DOMAIN][entry.entry_id].last_update_success


async def test_fix_lists_scgi_entries(
    hass: HomeAssistant,
    abus_controller: FakeAbusController,
    supervisor: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the fix warns about entries that still use the scgi server."""
    await _setup(hass, direct_entry())
    mock_config_entry.add_to_hass(hass)

    result = await _start_fix_flow(hass)

    assert result["step_id"] == "confirm_scgi"
    assert result["description_placeholders"] == {
        "app": "CybroScgiServer",
        "entries": mock_config_entry.title,
    }


async def test_fix_stop_failed(
    hass: HomeAssistant, abus_controller: FakeAbusController, supervisor: MagicMock
) -> None:
    """Test a failed stop aborts, the issue stays."""
    supervisor.addons.stop_addon.side_effect = SupervisorError("boom")
    await _setup(hass, direct_entry())

    result = await _confirm(hass, await _start_fix_flow(hass))

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "stop_failed"
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_PORT_IN_USE) is not None


async def test_fix_port_still_in_use(
    hass: HomeAssistant, abus_controller: FakeAbusController, supervisor: MagicMock
) -> None:
    """Test the fix aborts if another program still holds the port."""
    supervisor.addons.stop_addon.side_effect = lambda _: setattr(
        supervisor.app, "state", AddonState.STOPPED
    )
    entry = direct_entry()
    await _setup(hass, entry)

    result = await _confirm(hass, await _start_fix_flow(hass))

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "still_in_use"
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_PORT_IN_USE)
    # the app is stopped now, so the issue can't be fixed this way any more
    assert issue.translation_key == "port_in_use"
    assert entry.state is ConfigEntryState.LOADED


async def test_port_left_to_running_app(
    hass: HomeAssistant, abus_controller: FakeAbusController, supervisor: MagicMock
) -> None:
    """Test the port isn't taken from the app, even before the app binds it."""
    supervisor.addons.stop_addon.side_effect = lambda _: setattr(
        supervisor.app, "state", AddonState.STOPPED
    )
    free = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    free.bind(("127.0.0.1", 0))
    port = free.getsockname()[1]
    free.close()
    entry = direct_entry()

    with patch(f"{TRANSPORT}.LOCAL_PORT", port):
        await _setup(hass, entry)

        assert async_current_transport(hass).local_addr[1] != port
        issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_PORT_IN_USE)
        assert issue.is_fixable
        assert issue.translation_placeholders == {
            "port": str(port),
            "app": "CybroScgiServer",
        }

        result = await _confirm(hass, await _start_fix_flow(hass))

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert async_current_transport(hass).local_addr[1] == port
    assert entry.state is ConfigEntryState.LOADED


async def test_warning_logged_after_restart(
    hass: HomeAssistant,
    abus_controller: FakeAbusController,
    busy_port: socket.socket,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the issue stored by the last run doesn't hide the warning."""
    registry = ir.async_get(hass)
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_PORT_IN_USE,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_PORT_IN_USE,
    )
    # how Home Assistant loads it after a restart
    key = (DOMAIN, ISSUE_PORT_IN_USE)
    registry.issues[key] = replace(registry.issues[key], active=False)

    await _setup(hass, direct_entry())

    assert [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING and "is in use" in r.getMessage()
    ]
    assert registry.async_get_issue(DOMAIN, ISSUE_PORT_IN_USE).active


async def test_fix_stops_all_apps(
    hass: HomeAssistant, abus_controller: FakeAbusController, supervisor: MagicMock
) -> None:
    """Test every running app with the A-bus port is stopped (Edge Toolkit too)."""
    supervisor.addons.list.return_value.append(_app(TOOLKIT_SLUG, "Cybro Edge Toolkit"))
    entry = direct_entry()
    await _setup(hass, entry)

    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_PORT_IN_USE)
    assert issue.data == {"slugs": f"{APP_SLUG},{TOOLKIT_SLUG}"}
    assert issue.translation_placeholders["app"] == (
        "CybroScgiServer, Cybro Edge Toolkit"
    )

    result = await _confirm(hass, await _start_fix_flow(hass))

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert [c.args[0] for c in supervisor.addons.stop_addon.await_args_list] == [
        APP_SLUG,
        TOOLKIT_SLUG,
    ]
    assert [c.args for c in supervisor.addons.set_addon_options.await_args_list] == [
        (APP_SLUG, AddonsOptions(boot=AddonBoot.MANUAL)),
        (TOOLKIT_SLUG, AddonsOptions(boot=AddonBoot.MANUAL)),
    ]
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_PORT_IN_USE) is None
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("app", "found"),
    [
        (_app("85493909_cybroscgiserver", "CybroScgiServer"), True),
        (_app("85493909_cybroedgetoolkit", "Cybro Edge Toolkit"), True),
        # any app that declares the port, whatever its name
        (_app("a1b2c3d4_abus_bridge", "A-bus bridge"), True),
        (_app("local_mapped", "Mapped", lambda port: {"9000/udp": port}, False), True),
        (_app("local_other", "Other", lambda _: {"22/tcp": 22}), False),
        (_app("local_none", "No ports", None), False),
        # without host network the container port isn't the host port
        (
            _app("local_moved", "Moved", lambda port: {f"{port}/udp": 9000}, False),
            False,
        ),
        (
            _app("local_off", "Off", lambda port: {f"{port}/udp": None}, False),
            False,
        ),
    ],
    ids=lambda value: value.slug if isinstance(value, MagicMock) else None,
)
async def test_app_found_by_port(
    hass: HomeAssistant,
    abus_controller: FakeAbusController,
    supervisor: MagicMock,
    app: MagicMock,
    found: bool,
) -> None:
    """Test an app is found by the A-bus port it declares, not by its name."""
    supervisor.addons.list.return_value = [app]

    await _setup(hass, direct_entry())

    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_PORT_IN_USE)
    assert issue.is_fixable is found
    if found:
        assert issue.data == {"slugs": app.slug}


async def test_port_taken_when_free_again(
    hass: HomeAssistant, abus_controller: FakeAbusController, busy_port: socket.socket
) -> None:
    """Test the scan binds the A-bus port once it is free (no reload needed)."""
    entry = direct_entry()
    await _setup(hass, entry)
    fallback = async_current_transport(hass)
    assert fallback.local_addr[1] != transport.LOCAL_PORT

    busy_port.close()
    await async_discover(hass, {})
    await hass.async_block_till_done()

    assert async_current_transport(hass).local_addr[1] == transport.LOCAL_PORT
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_PORT_IN_USE) is None
    assert entry.state is ConfigEntryState.LOADED


async def test_port_not_taken_from_app(
    hass: HomeAssistant,
    abus_controller: FakeAbusController,
    supervisor: MagicMock,
    busy_port: socket.socket,
) -> None:
    """Test the scan leaves the port to a running app, even if it is free."""
    await _setup(hass, direct_entry())
    fallback = async_current_transport(hass)
    # the app hasn't bound the port yet
    busy_port.close()

    await async_discover(hass, {})

    assert async_current_transport(hass) is fallback


@pytest.mark.parametrize("failing", ["list", "addon_info"])
async def test_port_not_taken_while_apps_unknown(
    hass: HomeAssistant,
    abus_controller: FakeAbusController,
    supervisor: MagicMock,
    busy_port: socket.socket,
    failing: str,
) -> None:
    """Test the port isn't taken while the apps can't be checked, later it is."""
    busy_port.close()
    call = getattr(supervisor.addons, failing)
    working, call.side_effect = call.side_effect, SupervisorError("boom")
    entry = direct_entry()

    await _setup(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert async_current_transport(hass).local_addr[1] != transport.LOCAL_PORT
    # no conflict is known
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_PORT_IN_USE) is None
    await async_discover(hass, {})
    assert async_current_transport(hass).local_addr[1] != transport.LOCAL_PORT

    # the apps can be checked again, the app isn't running any more
    call.side_effect = working
    supervisor.app.state = AddonState.STOPPED
    await async_discover(hass, {})
    await hass.async_block_till_done()

    assert async_current_transport(hass).local_addr[1] == transport.LOCAL_PORT
