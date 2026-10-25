"""Tests for HIQ-Home scenes."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.hiq.const import DOMAIN

from .common import call_service, refresh, setup_with_tags

# scene 0 and 3 are defined, scene 3 is active, all others are not defined
SCENE_TAGS = {f"scene_status[{index}]": "-1" for index in range(32)} | {
    "scene_status[0]": "0",
    "scene_status[3]": "1",
    "global_scene_request": "0",
    "global_memory_request": "0",
}
SCENE_0 = "scene.c1000_scenes_scene_0"
SCENE_3 = "scene.c1000_scenes_scene_3"
STORE_3 = "button.c1000_scenes_store_scene_3"


async def test_defined_scenes_found(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test a scene is created for every defined scene."""
    await setup_with_tags(hass, aioclient_mock, mock_config_entry, SCENE_TAGS)

    assert sorted(hass.states.async_entity_ids("scene")) == [SCENE_0, SCENE_3]
    assert hass.states.get(SCENE_0).attributes["active"] is False
    assert hass.states.get(SCENE_3).attributes["active"] is True
    assert hass.states.get(SCENE_3).attributes["variable"] == "c1000.scene_status[3]"


async def test_activate_scene(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test activating a scene writes its index to the scene request."""
    controller = await setup_with_tags(
        hass, aioclient_mock, mock_config_entry, SCENE_TAGS
    )

    await call_service(hass, "scene", "turn_on", SCENE_3)

    assert controller.written("c1000.global_scene_request") == ["3"]


async def test_scene_active_follows_controller(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test the active attribute follows the scene status."""
    controller = await setup_with_tags(
        hass, aioclient_mock, mock_config_entry, SCENE_TAGS
    )

    controller.values["c1000.scene_status[0]"] = "1"
    controller.values["c1000.scene_status[3]"] = "0"
    await refresh(hass, mock_config_entry)

    assert hass.states.get(SCENE_0).attributes["active"] is True
    assert hass.states.get(SCENE_3).attributes["active"] is False


async def test_memorize_scene(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test the store button writes the scene index to the memory request."""
    controller = await setup_with_tags(
        hass, aioclient_mock, mock_config_entry, SCENE_TAGS
    )

    await call_service(hass, "button", "press", STORE_3)

    assert controller.written("c1000.global_memory_request") == ["3"]
    assert controller.written("c1000.global_scene_request") == []


async def test_memorize_button_disabled_by_default(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the store buttons are config entities, disabled by default."""
    await setup_with_tags(hass, aioclient_mock, mock_config_entry, SCENE_TAGS)

    entry = er.async_get(hass).async_get(STORE_3)
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entry.entity_category is er.EntityCategory.CONFIG


async def test_undefined_scenes_not_polled(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test only the status of defined scenes is polled after setup."""
    await setup_with_tags(hass, aioclient_mock, mock_config_entry, SCENE_TAGS)

    calls = len(aioclient_mock.mock_calls)
    await hass.data[DOMAIN][mock_config_entry.entry_id].async_refresh()
    await hass.async_block_till_done()
    polled = " ".join(str(call[1]) for call in aioclient_mock.mock_calls[calls:])

    assert "scene_status%5B3%5D" in polled or "scene_status[3]" in polled
    assert "scene_status%5B1%5D" not in polled
    assert "scene_status[1]" not in polled


async def test_no_scenes(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test a controller without scene status has no scenes."""
    await setup_with_tags(hass, aioclient_mock, mock_config_entry, {})

    assert hass.states.async_entity_ids("scene") == []
    assert hass.states.async_entity_ids("button") == []
