"""Tests for finding a controller by DHCP (Cybrotech MAC address)."""

from __future__ import annotations

import json

import pytest
from cybro.abus import PlcStatus
from cybro.testing import FakeAbusController
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hiq.const import DOMAIN
from custom_components.hiq.transport import async_current_transport

from .const import NAD, UNIQUE_ID
from .fake_abus import direct_entry
from .test_consistency import INTEGRATION

# MAC of c10000 (docs/abus-notes.md)
MAC = "00cb000050f2"


async def _dhcp(hass: HomeAssistant, ip: str = "127.0.0.1") -> dict:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(ip=ip, hostname="", macaddress=MAC),
    )
    await hass.async_block_till_done()
    return result


def test_manifest_matches_cybrotech_mac() -> None:
    """Test DHCP discovery matches the MAC prefix of the controllers (spike S4)."""
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())

    assert manifest["dhcp"] == [{"macaddress": "00CB00*"}]


async def test_dhcp_offers_controller(
    hass: HomeAssistant, hiq_controller: FakeAbusController
) -> None:
    """Test the NAD of the controller with the DHCP address is found and offered."""
    result = await _dhcp(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"] == {
        "nad": str(NAD),
        "ip": "127.0.0.1",
        "version": "6.1.1",
    }
    flow = hass.config_entries.flow.async_get(result["flow_id"])
    assert flow["context"]["unique_id"] == UNIQUE_ID
    # the scan socket is closed again
    assert async_current_transport(hass) is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].options == {"address": NAD, "connection": "direct"}


@pytest.mark.parametrize("problem", ["other_ip", "not_hiq", "stopped"])
async def test_dhcp_not_offered(
    hass: HomeAssistant, hiq_controller: FakeAbusController, problem: str
) -> None:
    """Test a device without running HIQ program at that IP isn't offered."""
    ip = "127.0.0.1"
    if problem == "other_ip":
        # eg: another Cybrotech device that doesn't answer the scan
        ip = "127.0.0.5"
    elif problem == "not_hiq":
        hiq_controller["program_id"] = 5
    else:
        hiq_controller.plc_status = PlcStatus.STOP

    result = await _dhcp(hass, ip)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_hiq"


async def test_dhcp_updates_static_ip(
    hass: HomeAssistant, hiq_controller: FakeAbusController
) -> None:
    """Test a new DHCP address of a direct entry is stored."""
    entry = direct_entry(ip_address="127.0.0.9")
    entry.add_to_hass(hass)

    result = await _dhcp(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.options["ip_address"] == "127.0.0.1"


async def test_dhcp_offers_switch(
    hass: HomeAssistant,
    hiq_controller: FakeAbusController,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the controller of an scgi entry is offered the direct connection."""
    mock_config_entry.add_to_hass(hass)

    result = await _dhcp(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_switch"
