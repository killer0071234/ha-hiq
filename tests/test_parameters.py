"""Tests for the parameters of the HIQ-Home light and blind outputs."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.hiq.const import DOMAIN

from .common import call_service, refresh, setup_with_tags

TAGS = {
    # LC-10-IQ
    "lc00_general_error": "0",
    "lc00_qx03": "0",
    "lc00_input_mode_03": "1",
    "lc00_output_mode_03": "60",
    "lc00_input_mode_index": "0",
    "lc00_input_mode_data": "0",
    "lc00_input_mode_req": "0",
    "lc00_output_mode_index": "0",
    "lc00_output_mode_data": "0",
    "lc00_output_mode_req": "0",
    # LD-10-IQ
    "ld00_general_error": "0",
    "ld00_qw02": "0",
    "ld00_input_mode_02": "0",
    "ld00_output_timer_02": "0",
    "ld00_color_mode_02": "2",
    "ld00_config_group": "0",
    "ld00_config_index": "0",
    "ld00_config_data": "0",
    "ld00_config_req": "0",
    # BC-5-IQ
    "bc00_general_error": "0",
    "bc00_blinds_position_01": "0",
    "bc00_blinds_time_up_01": "300",
    "bc00_blinds_time_dn_01": "280",
    "bc00_blinds_time_index": "0",
    "bc00_blinds_time_data": "0",
    "bc00_blinds_time_req": "0",
    # module with a general error -> no parameters
    "lc01_general_error": "1",
    "lc01_input_mode_00": "0",
}


def _entity_id(hass: HomeAssistant, domain: str, tag: str) -> str:
    """Return the entity id of the entity of a controller variable."""
    entity_id = er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"c1000.{tag}")
    assert entity_id is not None, tag
    return entity_id


async def test_parameters_found(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test parameters are found for working modules, on the output's device."""
    await setup_with_tags(hass, aioclient_mock, mock_config_entry, TAGS)
    registry = er.async_get(hass)

    def unique_ids(domain: str) -> list[str]:
        """Return the unique ids of all entities of a domain."""
        return sorted(
            e.unique_id for e in registry.entities.values() if e.domain == domain
        )

    assert unique_ids("select") == [
        "c1000.lc00_input_mode_03",
        "c1000.ld00_color_mode_02",
        "c1000.ld00_input_mode_02",
    ]
    assert unique_ids("number") == [
        "c1000.bc00_blinds_time_dn_01",
        "c1000.bc00_blinds_time_up_01",
        "c1000.lc00_output_mode_03",
        "c1000.ld00_output_timer_02",
    ]
    for domain, tag, output in (
        ("select", "lc00_input_mode_03", ("light", "lc00_qx03")),
        ("select", "ld00_color_mode_02", ("light", "ld00_qw02")),
        ("number", "bc00_blinds_time_up_01", ("cover", "bc00_blinds_position_01")),
    ):
        assert (
            registry.async_get(_entity_id(hass, domain, tag)).device_id
            == registry.async_get(_entity_id(hass, *output)).device_id
        )


async def test_parameters_read(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test parameter values are read from their own variable."""
    await setup_with_tags(hass, aioclient_mock, mock_config_entry, TAGS)

    for domain, tag, state in (
        ("select", "lc00_input_mode_03", "staircase"),
        ("select", "ld00_color_mode_02", "white_temperature"),
        ("number", "lc00_output_mode_03", "60"),
        ("number", "bc00_blinds_time_up_01", "30.0"),
        ("number", "bc00_blinds_time_dn_01", "28.0"),
    ):
        assert hass.states.get(_entity_id(hass, domain, tag)).state == state, tag


@pytest.mark.parametrize(
    ("domain", "tag", "data", "expected"),
    [
        (
            "select",
            "lc00_input_mode_03",
            {"option": "motion_night"},
            [
                ("c1000.lc00_input_mode_index", "3"),
                ("c1000.lc00_input_mode_data", "3"),
                ("c1000.lc00_input_mode_req", "1"),
            ],
        ),
        (
            "number",
            "lc00_output_mode_03",
            {"value": 120},
            [
                ("c1000.lc00_output_mode_index", "3"),
                ("c1000.lc00_output_mode_data", "120"),
                ("c1000.lc00_output_mode_req", "1"),
            ],
        ),
        (
            "select",
            "ld00_input_mode_02",
            {"option": "event_only"},
            [
                ("c1000.ld00_config_group", "0"),
                ("c1000.ld00_config_index", "2"),
                ("c1000.ld00_config_data", "7"),
                ("c1000.ld00_config_req", "1"),
            ],
        ),
        (
            "number",
            "ld00_output_timer_02",
            {"value": 9999},
            [
                ("c1000.ld00_config_group", "1"),
                ("c1000.ld00_config_index", "2"),
                ("c1000.ld00_config_data", "9999"),
                ("c1000.ld00_config_req", "1"),
            ],
        ),
        (
            "select",
            "ld00_color_mode_02",
            {"option": "rgb"},
            [
                ("c1000.ld00_config_group", "2"),
                ("c1000.ld00_config_index", "2"),
                ("c1000.ld00_config_data", "1"),
                ("c1000.ld00_config_req", "1"),
            ],
        ),
        (
            "number",
            "bc00_blinds_time_up_01",
            {"value": 25.5},
            [
                ("c1000.bc00_blinds_time_index", "1"),
                ("c1000.bc00_blinds_time_data", "255"),
                ("c1000.bc00_blinds_time_req", "1"),
            ],
        ),
        (
            "number",
            "bc00_blinds_time_dn_01",
            {"value": 20},
            [
                ("c1000.bc00_blinds_time_index", "6"),
                ("c1000.bc00_blinds_time_data", "200"),
                ("c1000.bc00_blinds_time_req", "1"),
            ],
        ),
    ],
)
async def test_parameter_written_through_shared_registers(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
    domain: str,
    tag: str,
    data: dict,
    expected: list[tuple[str, str]],
) -> None:
    """Test a parameter is written by selecting the output, data and request."""
    controller = await setup_with_tags(hass, aioclient_mock, mock_config_entry, TAGS)
    service = "select_option" if domain == "select" else "set_value"

    await call_service(hass, domain, service, _entity_id(hass, domain, tag), **data)

    assert controller.writes == expected


async def test_parameters_disabled_and_not_polled(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test parameters are disabled by default and then not polled."""
    await setup_with_tags(hass, aioclient_mock, mock_config_entry, TAGS)

    entry = er.async_get(hass).async_get(
        _entity_id(hass, "select", "lc00_input_mode_03")
    )
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entry.entity_category is er.EntityCategory.CONFIG

    calls = len(aioclient_mock.mock_calls)
    await refresh(hass, mock_config_entry)
    polled = " ".join(str(call[1]) for call in aioclient_mock.mock_calls[calls:])
    assert "c1000.lc00_qx03" in polled
    for tag in ("_input_mode_", "_output_mode_", "_output_timer_", "_blinds_time_"):
        assert tag not in polled
