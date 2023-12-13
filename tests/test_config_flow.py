"""Test the HIQ config flow."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry
from .helper import get_cybro_device
from custom_components.hiq.const import DOMAIN
from cybro import Device, CybroConnectionError
from homeassistant import config_entries, setup
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_ADDRESS,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    HOST,
    PORT,
    NAD,
    CONFIG_ENTRY_ID,
)


async def test_full_user_flow_implementation(
    hass: HomeAssistant,
    # mock_setup_entry: None,
    # mock_config_entry_v1: MockConfigEntry,
):
    """Test we get the form."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "custom_components.hiq.config_flow.HiqFlowHandler._async_get_device",
        return_value=get_cybro_device(),
    ), patch(
        "custom_components.hiq.coordinator.HiqDataUpdateCoordinator._async_update_data",
        return_value=get_cybro_device(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_ADDRESS: NAD,
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["handler"] == DOMAIN
        data = result2["data"]
        assert data[CONF_HOST] == HOST
        assert data[CONF_PORT] == PORT
        assert data[CONF_ADDRESS] == NAD


async def test_user_flow_connection_error(
    hass: HomeAssistant,
    # mock_setup_entry: None,
    # mock_config_entry_v1: MockConfigEntry,
):
    """Test we get the form."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "custom_components.hiq.config_flow.HiqFlowHandler._async_get_device",
        side_effect=CybroConnectionError(""),
    ), patch(
        "custom_components.hiq.coordinator.HiqDataUpdateCoordinator._async_update_data",
        return_value=get_cybro_device(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_ADDRESS: NAD,
            },
        )
        await hass.async_block_till_done()

        assert result2["errors"]["base"] == "cannot_connect"
        assert result2["type"] == FlowResultType.FORM


async def test_user_flow_scgi_server_not_running(
    hass: HomeAssistant,
    # mock_setup_entry: None,
    # mock_config_entry_v1: MockConfigEntry,
):
    """Test we get the form."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "custom_components.hiq.coordinator.HiqDataUpdateCoordinator._async_update_data",
        return_value=get_cybro_device(),
    ), patch(
        "custom_components.hiq.config_flow.HiqFlowHandler._async_get_device",
        return_value=get_cybro_device({"sys.scgi_port_status": ""}),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_ADDRESS: NAD,
            },
        )
        await hass.async_block_till_done()
        print(result2)
        # assert result2["data"] == "scgi_server_not_running"
        assert result2["type"] == FlowResultType.ABORT


async def test_user_flow_plc_not_existing(
    hass: HomeAssistant,
    # mock_setup_entry: None,
    # mock_config_entry_v1: MockConfigEntry,
):
    """Test we get the form."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "custom_components.hiq.coordinator.HiqDataUpdateCoordinator._async_update_data",
        return_value=get_cybro_device(),
    ), patch(
        "custom_components.hiq.config_flow.HiqFlowHandler._async_get_device",
        return_value=get_cybro_device({"c1000.sys.plc_program_status": ""}),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_ADDRESS: NAD,
            },
        )
        await hass.async_block_till_done()
        print(result2)
        # assert result2["data"] == "scgi_server_not_running"
        assert result2["type"] == FlowResultType.ABORT


async def async_check_options_form(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> dict[str, Any]:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.async_init(mock_config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "custom_components.hiq.config_flow._async_get_device",
        return_value=Device(
            info="dummy",
            vars={"test": 123},
        ),
    ), patch(
        "custom_components.hiq.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.FORM
        assert result2["handler"] == CONFIG_ENTRY_ID
        assert result2["step_id"] == "interface"

        next(
            flow
            for flow in hass.config_entries.options.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )

        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"],
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["handler"] == CONFIG_ENTRY_ID
    assert result3["title"] == ""
    return mock_config_entry.data
