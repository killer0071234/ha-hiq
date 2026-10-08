"""Helpers for the HIQ-Home tests."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.hiq.const import DOMAIN

from .fake_controller import FakeController


async def call_service(
    hass: HomeAssistant, domain: str, service: str, entity_id: str, **data: Any
) -> None:
    """Call an entity service and wait until it is done."""
    await hass.services.async_call(
        domain, service, {"entity_id": entity_id, **data}, blocking=True
    )
    await hass.async_block_till_done()


async def refresh(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Poll the controller and update all entity states."""
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    await hass.async_block_till_done()


async def setup_with_tags(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entry: MockConfigEntry,
    tags: dict[str, str],
) -> FakeController:
    """Set up the integration with a controller holding only the given tags."""
    controller = FakeController(tags)
    controller.register(aioclient_mock)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await refresh(hass, entry)
    return controller
