"""Tests for HIQ-Home sensors found on controllers with special tags."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.hiq.const import DOMAIN

from .common import setup_with_tags


async def test_power_meter_energy(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test energy counters are total increasing, the real energy in Wh resolution."""
    await setup_with_tags(
        hass,
        aioclient_mock,
        mock_config_entry,
        {
            "power_meter_error": "0",
            "power_meter_energy": "123",
            "power_meter_energy_real": "120.1826171875",
            "power_meter_energy_watthours": "4567",
        },
    )

    entity_registry = er.async_get(hass)
    states = {}
    for tag in (
        "power_meter_energy",
        "power_meter_energy_real",
        "power_meter_energy_watthours",
    ):
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"c1000.{tag}"
        )
        state = hass.states.get(entity_id)
        states[tag] = (
            state.state,
            state.attributes["unit_of_measurement"],
            state.attributes["state_class"],
        )
    assert states == {
        "power_meter_energy": ("123", "kWh", "total_increasing"),
        "power_meter_energy_real": ("120.183", "kWh", "total_increasing"),
        "power_meter_energy_watthours": ("4567", "Wh", "total_increasing"),
    }


async def test_power_meter_energy_real_disabled_by_default(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the real energy is disabled by default, it duplicates the energy."""
    await setup_with_tags(
        hass,
        aioclient_mock,
        mock_config_entry,
        {
            "power_meter_error": "0",
            "power_meter_energy": "15787",
            "power_meter_energy_real": "15787.1826171875",
        },
    )

    entity_registry = er.async_get(hass)
    disabled = {
        tag: entity_registry.async_get(
            entity_registry.async_get_entity_id("sensor", DOMAIN, f"c1000.{tag}")
        ).disabled_by
        for tag in ("power_meter_energy", "power_meter_energy_real")
    }
    assert disabled == {
        "power_meter_energy": None,
        "power_meter_energy_real": er.RegistryEntryDisabler.INTEGRATION,
    }


@pytest.mark.parametrize(
    "error_tags",
    [{"power_meter_error": "1"}, {}],
    ids=["meter_error", "no_error_variable"],
)
async def test_power_meter_not_ok(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
    error_tags: dict[str, str],
) -> None:
    """Test no power meter sensors are created when the meter is not ok."""
    await setup_with_tags(
        hass,
        aioclient_mock,
        mock_config_entry,
        {**error_tags, "power_meter_power": "1200", "power_meter_energy": "123"},
    )

    assert [
        entity_id
        for entity_id in hass.states.async_entity_ids("sensor")
        if "power_meter" in entity_id
    ] == []


async def test_thermostat_max_timer(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test the remaining time of the max function is a duration in seconds."""
    await setup_with_tags(
        hass,
        aioclient_mock,
        mock_config_entry,
        {"th00_general_error": "0", "th00_max_timer": "90"},
    )

    state = hass.states.get(
        "sensor.climate_c1000_th00_thermostat_max_function_remain_timer"
    )
    assert state.state == "90"
    assert state.attributes["unit_of_measurement"] == "s"
    assert state.attributes["device_class"] == "duration"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("outdoor_temperature", "12.5"),
        ("wall_temperature", "20.5"),
        ("water_temperature", "45.0"),
        ("auxiliary_temperature", "-3.0"),
    ],
)
async def test_hvac_temperatures(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
    name: str,
    value: str,
) -> None:
    """Test hvac temperatures are scaled by 0.1 °C."""
    await setup_with_tags(
        hass,
        aioclient_mock,
        mock_config_entry,
        {
            "outdoor_temperature": "125",
            "wall_temperature": "205",
            "water_temperature": "450",
            "auxilary_temperature": "-30",
        },
    )

    state = hass.states.get(f"sensor.climate_c1000_hvac_{name}")
    assert state.state == value
    assert state.attributes["unit_of_measurement"] == "°C"


async def test_hvac_temperatures_enabled_by_controller(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test hvac temperatures are only enabled when enabled on the controller."""
    await setup_with_tags(
        hass,
        aioclient_mock,
        mock_config_entry,
        {
            "outdoor_temperature": "125",
            "outdoor_temperature_enable": "1",
            "wall_temperature": "205",
            "wall_temperature_enable": "0",
            # no enable variable at all
            "water_temperature": "450",
        },
    )

    entity_registry = er.async_get(hass)
    disabled = {
        tag: entity_registry.async_get(
            entity_registry.async_get_entity_id("sensor", DOMAIN, f"c1000.{tag}")
        ).disabled
        for tag in ("outdoor_temperature", "wall_temperature", "water_temperature")
    }
    assert disabled == {
        "outdoor_temperature": False,
        "wall_temperature": True,
        "water_temperature": True,
    }


async def test_no_module_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test a controller without known variables only has its system sensors."""
    await setup_with_tags(hass, aioclient_mock, mock_config_entry, {})

    assert [
        entity_id
        for entity_id in hass.states.async_entity_ids("sensor")
        if not entity_id.startswith("sensor.system_")
    ] == []


async def test_power_meter_voltage_in_volts(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test a voltage reported in volts (not 0.1 V) is not scaled."""
    await setup_with_tags(
        hass,
        aioclient_mock,
        mock_config_entry,
        {"power_meter_error": "0", "power_meter_voltage": "231"},
    )

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, "c1000.power_meter_voltage"
    )
    assert hass.states.get(entity_id).state == "231"


async def test_enocean_general_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test the general error of the EnOcean module is named after it."""
    await setup_with_tags(
        hass, aioclient_mock, mock_config_entry, {"eno_general_error": "0"}
    )

    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, "c1000.eno_general_error"
    )
    state = hass.states.get(entity_id)
    assert state.attributes["friendly_name"] == "c1000 diagnostic EnOcean general error"
    assert state.state == "off"
