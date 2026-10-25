"""Tests for finding controllers on the LAN (A-bus broadcast scan)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from cybro.abus import PlcStatus
from cybro.testing import FakeAbusController
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.hiq.const import DOMAIN, SCAN_INTERVAL_DISCOVERY
from custom_components.hiq.discovery import async_discover
from custom_components.hiq.transport import async_current_transport

from .const import NAD, OPTIONS, TITLE, UNIQUE_ID
from .fake_abus import HIQ_PROGRAM, TRANSPORT, direct_entry, start_hiq_controller
from .fake_controller import HIQ_TAGS, FakeController

CUSTOM_SENSOR = {"tag": "lc00_qx00", "name": "Custom", "unique_id": "abc"}


async def _discover(hass: HomeAssistant, checked: dict | None = None) -> list[dict]:
    """Scan once and return the flows in progress."""
    await async_discover(hass, {} if checked is None else checked)
    # discovery flows start in background tasks
    await hass.async_block_till_done(wait_background_tasks=True)
    return hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def _configure(hass: HomeAssistant, flow_id: str, user_input: dict) -> dict:
    result = await hass.config_entries.flow.async_configure(flow_id, user_input)
    await hass.async_block_till_done()
    return result


async def test_discovered_controller_added(
    hass: HomeAssistant, hiq_controller: FakeAbusController
) -> None:
    """Test a HIQ controller is offered and added without static IP."""
    flows = await _discover(hass)

    assert len(flows) == 1
    flow = flows[0]
    assert flow["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY
    assert flow["context"]["unique_id"] == UNIQUE_ID
    assert flow["context"]["title_placeholders"] == {"name": f"c{NAD}"}
    assert flow["step_id"] == "discovery_confirm"
    result = hass.config_entries.flow.async_get(flow["flow_id"])
    assert result["context"]["title_placeholders"] == {"name": f"c{NAD}"}

    result = await _configure(hass, flow["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"c{NAD}"
    entry = result["result"]
    assert entry.unique_id == UNIQUE_ID
    assert entry.options == {"address": NAD, "connection": "direct"}
    assert entry.state is config_entries.ConfigEntryState.LOADED


async def test_confirm_shows_controller(
    hass: HomeAssistant, hiq_controller: FakeAbusController
) -> None:
    """Test the confirm form shows NAD, IP and HIQ program version."""
    await _discover(hass)
    flow = hass.config_entries.flow.async_progress_by_handler(DOMAIN)[0]

    result = await hass.config_entries.flow.async_configure(flow["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {
        "nad": str(NAD),
        "ip": "127.0.0.1",
        "version": "6.1.1",
    }


@pytest.mark.parametrize(
    "program",
    [
        {**HIQ_PROGRAM, "program_id": "5"},
        {},
    ],
    ids=["other_program", "no_program_id"],
)
async def test_only_hiq_controllers_offered(
    hass: HomeAssistant, socket_enabled: None, program: dict[str, str]
) -> None:
    """Test controllers without the HIQ program are skipped, and checked once."""
    fake = await start_hiq_controller(NAD, HIQ_TAGS | program)
    checked: dict = {}
    with (
        patch(f"{TRANSPORT}.BIND_HOST", "127.0.0.1"),
        patch(f"{TRANSPORT}.CONTROLLER_PORT", fake.port),
        patch(f"{TRANSPORT}.BROADCAST", "127.0.0.1"),
    ):
        assert await _discover(hass, checked) == []
        requests = len(fake.requests)
        assert await _discover(hass, checked) == []
    fake.close()

    # the second scan doesn't download the allocation table again
    assert len(fake.requests) == requests + 1
    assert checked == {NAD: None}


async def test_stopped_controller_not_offered(
    hass: HomeAssistant, hiq_controller: FakeAbusController
) -> None:
    """Test a controller without running program is checked again later."""
    hiq_controller.plc_status = PlcStatus.STOP
    checked: dict = {}

    assert await _discover(hass, checked) == []
    assert checked == {}

    hiq_controller.plc_status = PlcStatus.RUN
    assert len(await _discover(hass, checked)) == 1


async def test_confirm_with_password(
    hass: HomeAssistant, hiq_controller: FakeAbusController
) -> None:
    """Test a wrong A-bus password is shown, the right one is stored."""
    flow = (await _discover(hass))[0]
    hiq_controller.password = 1234

    result = await _configure(hass, flow["flow_id"], {"password": 4321})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "access_denied"}

    result = await _configure(hass, flow["flow_id"], {"password": 1234})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].options == {
        "address": NAD,
        "connection": "direct",
        "password": 1234,
    }


async def test_discovered_once(
    hass: HomeAssistant, hiq_controller: FakeAbusController
) -> None:
    """Test scanning again doesn't offer the controller twice."""
    checked: dict = {}
    await _discover(hass, checked)

    assert len(await _discover(hass, checked)) == 1


async def test_ignored_controller_not_offered_again(
    hass: HomeAssistant, hiq_controller: FakeAbusController
) -> None:
    """Test a controller the user ignored isn't offered again."""
    flow = (await _discover(hass))[0]
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IGNORE},
        data={"unique_id": flow["context"]["unique_id"], "title": f"c{NAD}"},
    )
    await hass.async_block_till_done()

    assert await _discover(hass) == []


@pytest.mark.parametrize(
    ("ip", "expected"),
    [("127.0.0.9", "127.0.0.1"), ("127.0.0.1", "127.0.0.1"), (None, None)],
    ids=["changed", "same", "broadcast"],
)
async def test_direct_entry_ip_updated(
    hass: HomeAssistant,
    hiq_controller: FakeAbusController,
    ip: str | None,
    expected: str | None,
) -> None:
    """Test a static IP is updated, a configured controller isn't offered."""
    entry = direct_entry(ip_address=ip)
    entry.add_to_hass(hass)

    assert await _discover(hass) == []
    assert entry.options.get("ip_address") == expected


async def test_switch_scgi_entry_to_direct(
    hass: HomeAssistant,
    controller: FakeController,
    hiq_controller: FakeAbusController,
) -> None:
    """Test an scgi entry of a found controller is offered the direct connection."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        title=TITLE,
        unique_id=UNIQUE_ID,
        options={**OPTIONS, "sensor": [CUSTOM_SENSOR]},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    entities = {
        e.entity_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }

    flows = await _discover(hass)
    assert len(flows) == 1
    assert flows[0]["step_id"] == "discovery_switch"
    assert flows[0]["context"]["unique_id"] == f"{UNIQUE_ID}_switch"

    result = await _configure(hass, flows[0]["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "switched"
    assert entry.title == f"c{NAD}"
    assert entry.unique_id == UNIQUE_ID
    assert entry.options == {
        "address": NAD,
        "connection": "direct",
        "sensor": [CUSTOM_SENSOR],
    }
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert type(hass.data[DOMAIN][entry.entry_id].cybro).__name__ == "CybroDirect"
    assert {
        e.entity_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    } == entities
    assert await _discover(hass) == []


async def test_ignored_switch_not_offered_again(
    hass: HomeAssistant,
    controller: FakeController,
    hiq_controller: FakeAbusController,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an ignored switch offer keeps the scgi entry and isn't offered again."""
    mock_config_entry.add_to_hass(hass)
    flow = (await _discover(hass))[0]
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IGNORE},
        data={"unique_id": flow["context"]["unique_id"], "title": f"c{NAD}"},
    )
    await hass.async_block_till_done()

    assert await _discover(hass) == []
    assert mock_config_entry.options["connection"] == "scgi"


async def test_scan_without_direct_entry(
    hass: HomeAssistant, hiq_controller: FakeAbusController
) -> None:
    """Test the scan opens a socket of its own and closes it again."""
    with patch(f"{TRANSPORT}.LOCAL_PORT", 1):  # would fail: the scan uses any port
        await _discover(hass)

    assert async_current_transport(hass) is None


async def test_scan_uses_shared_transport(
    hass: HomeAssistant, hiq_controller: FakeAbusController
) -> None:
    """Test the scan uses the socket of the direct entries, and keeps it open."""
    entry = direct_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    transport = async_current_transport(hass)

    with patch.object(transport, "close") as close:
        await _discover(hass)

    close.assert_not_called()
    assert any(frame.to_nad == 0 for frame in hiq_controller.requests)


async def test_scan_scheduled(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, controller: FakeController
) -> None:
    """Test the integration scans at start and then periodically."""
    with patch("custom_components.hiq.discovery.async_discover") as discover:
        mock_config_entry.add_to_hass(hass)
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert discover.call_count == 1

        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL_DISCOVERY)
        await hass.async_block_till_done()
        assert discover.call_count == 2


async def test_manual_flow_while_discovered(
    hass: HomeAssistant, hiq_controller: FakeAbusController
) -> None:
    """Test adding a discovered controller by hand points to the discovered flow."""
    await _discover(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "direct"}
    )

    result = await _configure(hass, result["flow_id"], {"address": NAD})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"
