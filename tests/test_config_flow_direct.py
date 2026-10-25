"""Tests for adding a controller directly and for switching the connection."""

from __future__ import annotations

from typing import Any

import pytest
from cybro.abus import PlcStatus
from cybro.testing import FakeAbusController
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hiq.const import DOMAIN
from custom_components.hiq.transport import async_current_transport

from .const import HOST, NAD, OPTIONS, PORT, TITLE, UNIQUE_ID, USER_INPUT
from .fake_abus import direct_entry
from .fake_controller import FakeController

DIRECT_INPUT = {"address": NAD, "ip_address": "127.0.0.1"}
DIRECT_OPTIONS = {"address": NAD, "connection": "direct", "ip_address": "127.0.0.1"}
CUSTOM_SENSOR = {"tag": "lc00_qx00", "name": "Custom", "unique_id": "abc"}


async def _start_direct_flow(hass: HomeAssistant) -> dict:
    """Start adding a controller directly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "direct"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "direct"
    return result


async def _configure(hass: HomeAssistant, result: dict, user_input: dict) -> dict:
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()
    return result


@pytest.mark.parametrize(
    ("user_input", "options"),
    [
        (DIRECT_INPUT, DIRECT_OPTIONS),
        ({"address": NAD}, {"address": NAD, "connection": "direct"}),
        (
            {**DIRECT_INPUT, "password": 1234},
            {**DIRECT_OPTIONS, "password": 1234},
        ),
    ],
    ids=["static_ip", "broadcast", "password"],
)
async def test_direct_flow(
    hass: HomeAssistant,
    abus_controller: FakeAbusController,
    user_input: dict[str, Any],
    options: dict[str, Any],
) -> None:
    """Test a running controller is added without scgi server."""
    if "password" in user_input:
        abus_controller.password = 1234
    result = await _start_direct_flow(hass)

    result = await _configure(hass, result, user_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"c{NAD}"
    entry = result["result"]
    assert entry.unique_id == UNIQUE_ID
    assert entry.data == {}
    assert entry.options == options
    assert entry.state is config_entries.ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("setup", "user_input", "errors"),
    [
        ("silent", DIRECT_INPUT, {"base": "no_answer"}),
        ("password", DIRECT_INPUT, {"base": "access_denied"}),
        ("stopped", DIRECT_INPUT, {"base": "no_program"}),
        (
            None,
            {**DIRECT_INPUT, "ip_address": "300.1.2.3"},
            {"ip_address": "invalid_ip"},
        ),
    ],
)
async def test_direct_flow_errors(
    hass: HomeAssistant,
    abus_controller: FakeAbusController,
    setup: str | None,
    user_input: dict[str, Any],
    errors: dict[str, str],
) -> None:
    """Test problems are shown in the form, and it can be submitted again."""
    if setup == "silent":
        abus_controller.silent = True
    elif setup == "password":
        abus_controller.password = 4321
    elif setup == "stopped":
        abus_controller.plc_status = PlcStatus.STOP
    result = await _start_direct_flow(hass)

    result = await _configure(hass, result, user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors
    # the socket of the flow is closed again
    assert async_current_transport(hass) is None

    abus_controller.silent = False
    abus_controller.password = None
    abus_controller.plc_status = PlcStatus.RUN
    result = await _configure(hass, result, DIRECT_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_direct_flow_already_configured(
    hass: HomeAssistant,
    abus_controller: FakeAbusController,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a controller set up through the scgi server can't be added again."""
    mock_config_entry.add_to_hass(hass)
    result = await _start_direct_flow(hass)

    result = await _configure(hass, result, DIRECT_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def _suggested(result: dict) -> dict[str, Any]:
    """Return the suggested values of a form."""
    return {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }


async def _start_reconfigure(
    hass: HomeAssistant, entry: MockConfigEntry, step: str
) -> dict:
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["reconfigure_direct", "reconfigure_scgi"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step
    return result


async def test_reconfigure_scgi_to_direct(
    hass: HomeAssistant,
    controller: FakeController,
    abus_controller: FakeAbusController,
) -> None:
    """Test an scgi entry switches to direct, keeping custom entities."""
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
    entities = {
        e.entity_id
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    }

    result = await _start_reconfigure(hass, entry, "reconfigure_direct")
    assert _suggested(result) == {"address": NAD}
    result = await _configure(hass, result, DIRECT_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.title == f"c{NAD}"
    assert entry.options == {**DIRECT_OPTIONS, "sensor": [CUSTOM_SENSOR]}
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert type(hass.data[DOMAIN][entry.entry_id].cybro).__name__ == "CybroDirect"
    assert {
        e.entity_id
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    } == entities


async def test_reconfigure_direct_to_scgi(
    hass: HomeAssistant,
    controller: FakeController,
    abus_controller: FakeAbusController,
) -> None:
    """Test a direct entry switches to the scgi server."""
    entry = direct_entry(password=1234)
    abus_controller.password = 1234
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await _start_reconfigure(hass, entry, "reconfigure_scgi")
    result = await _configure(hass, result, USER_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.title == f"c{NAD}@{HOST}:{PORT}"
    assert entry.options == OPTIONS
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert async_current_transport(hass) is None


async def test_reconfigure_other_controller(
    hass: HomeAssistant,
    abus_controller: FakeAbusController,
) -> None:
    """Test reconfiguring can't switch the entry to another controller."""
    entry = direct_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await _start_reconfigure(hass, entry, "reconfigure_direct")
    result = await _configure(hass, result, {**DIRECT_INPUT, "address": NAD + 1})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_controller"
    assert entry.options == DIRECT_OPTIONS


async def test_reconfigure_error_shown(
    hass: HomeAssistant,
    abus_controller: FakeAbusController,
) -> None:
    """Test a controller that doesn't answer keeps the reconfigure form open."""
    entry = direct_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await _start_reconfigure(hass, entry, "reconfigure_direct")
    abus_controller.silent = True
    result = await _configure(hass, result, DIRECT_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_answer"}


async def _start_direct(hass: HomeAssistant) -> dict:
    """Choose the direct connection in the user menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return await _configure(hass, result, {"next_step_id": "direct"})


def _choices(result: dict) -> list[dict[str, str]]:
    return result["data_schema"].schema["controller"].config["options"]


async def test_direct_flow_lists_found_controllers(
    hass: HomeAssistant, hiq_controller: FakeAbusController
) -> None:
    """Test the HIQ controllers on the LAN are offered first (first setup)."""
    result = await _start_direct(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "direct_pick"
    assert _choices(result) == [
        {"value": str(NAD), "label": f"c{NAD} (127.0.0.1, HIQ 6.1.1)"},
        {"value": "manual", "label": "manual"},
    ]

    result = await _configure(hass, result, {"controller": str(NAD)})
    assert result["step_id"] == "discovery_confirm"
    result = await _configure(hass, result, {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == UNIQUE_ID
    assert result["result"].options == {"address": NAD, "connection": "direct"}


async def test_direct_flow_pick_manual(
    hass: HomeAssistant, hiq_controller: FakeAbusController
) -> None:
    """Test the NAD can still be entered by hand."""
    result = await _start_direct(hass)

    result = await _configure(hass, result, {"controller": "manual"})
    assert result["step_id"] == "direct"
    result = await _configure(hass, result, DIRECT_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_direct_flow_skips_configured(
    hass: HomeAssistant, hiq_controller: FakeAbusController
) -> None:
    """Test a controller that is set up isn't listed, the form is shown."""
    direct_entry().add_to_hass(hass)

    result = await _start_direct(hass)

    assert result["step_id"] == "direct"


async def test_direct_flow_lists_ignored(
    hass: HomeAssistant, hiq_controller: FakeAbusController
) -> None:
    """Test a controller ignored under Discovered can still be added here."""
    MockConfigEntry(
        domain=DOMAIN, source=config_entries.SOURCE_IGNORE, unique_id=UNIQUE_ID
    ).add_to_hass(hass)

    result = await _start_direct(hass)
    result = await _configure(hass, result, {"controller": str(NAD)})
    result = await _configure(hass, result, {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
