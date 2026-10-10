"""Tests for the HIQ-Home custom select entities."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.hiq.const import DOMAIN

from .common import call_service, refresh, setup_with_tags
from .const import NAD, OPTIONS, TITLE

CUSTOM_SELECT = {
    # the tag has the translation key of a built-in select
    "tag": "hvac_mode",
    "name": "Heating mode",
    "unique_id": "abc",
    "options": {"off": 0, "eco": 1, "frost": -1, "comfort": 5},
}


def _entry(**options: object) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title=TITLE,
        unique_id=TITLE,
        options={**OPTIONS, **options},
    )


async def _setup_custom_select(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, value: str
):
    entry = _entry(select=[CUSTOM_SELECT])
    controller = await setup_with_tags(
        hass, aioclient_mock, entry, {"hvac_mode": value}
    )
    entity_id = er.async_get(hass).async_get_entity_id("select", DOMAIN, "abc")
    assert entity_id is not None
    return entry, controller, entity_id


async def test_custom_select_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a custom select shows the label of the controller value."""
    _, _, entity_id = await _setup_custom_select(hass, aioclient_mock, "5")

    state = hass.states.get(entity_id)
    assert state.state == "comfort"
    assert state.name.endswith("Heating mode")
    assert state.attributes["options"] == ["off", "eco", "frost", "comfort"]
    assert state.attributes["variable"] == f"c{NAD}.hvac_mode"


async def test_custom_select_on_custom_device(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a custom select is enabled and belongs to the custom device."""
    _, _, entity_id = await _setup_custom_select(hass, aioclient_mock, "0")

    entity = er.async_get(hass).async_get(entity_id)
    assert entity.disabled_by is None
    assert entity.entity_category is None
    device = dr.async_get(hass).async_get(entity.device_id)
    assert (DOMAIN, f"{NAD} custom") in device.identifiers


async def test_custom_select_unknown_value(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a controller value without option is unknown."""
    _, _, entity_id = await _setup_custom_select(hass, aioclient_mock, "3")

    assert hass.states.get(entity_id).state == "unknown"


async def test_custom_select_option(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test selecting an option writes its value, negative values included."""
    entry, controller, entity_id = await _setup_custom_select(hass, aioclient_mock, "0")

    await call_service(hass, "select", "select_option", entity_id, option="frost")
    await refresh(hass, entry)

    assert controller.written(f"c{NAD}.hvac_mode") == ["-1"]
    assert hass.states.get(entity_id).state == "frost"


async def test_no_custom_selects(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an entry without custom selects sets up without them."""
    entry = _entry()
    await setup_with_tags(hass, aioclient_mock, entry, {"hvac_mode": "0"})

    assert hass.states.async_entity_ids("select") == []
