"""Fixtures for the HIQ-Home tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
from unittest.mock import PropertyMock, patch

import backoff._async
import pytest
from cybro.testing import FakeAbusController
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.hiq.const import DOMAIN

from .const import NAD, OPTIONS, TITLE, UNIQUE_ID
from .fake_abus import TRANSPORT, start_hiq_controller
from .fake_controller import FakeController


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading the integration from custom_components."""


class _NoSleepAsyncio:
    """asyncio proxy without delays, used by backoff between retries."""

    def __getattr__(self, name: str) -> object:
        return getattr(asyncio, name)

    async def sleep(self, *args: object) -> None:
        """Do not wait between retries."""


@pytest.fixture(autouse=True)
def no_backoff_delay() -> Generator[None]:
    """Let cybro retry failed requests without waiting."""
    with patch.object(backoff._async, "asyncio", _NoSleepAsyncio()):
        yield


@pytest.fixture(autouse=True)
def no_discovery_scan() -> Generator[None]:
    """Don't scan the LAN on the integration's schedule.

    The discovery tests call async_discover themselves.
    """
    with patch("custom_components.hiq.discovery.async_discover"):
        yield


@pytest.fixture
def enable_all_entities() -> Generator[None]:
    """Create entities that are disabled by default as enabled."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        new_callable=PropertyMock,
        return_value=True,
    ):
        yield


@pytest.fixture
def controller(aioclient_mock: AiohttpClientMocker) -> FakeController:
    """Return a fake SCGI server with one HIQ controller."""
    fake = FakeController()
    fake.register(aioclient_mock)
    return fake


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for the fake controller."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        title=TITLE,
        unique_id=UNIQUE_ID,
        data={},
        options=OPTIONS,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    controller: FakeController,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> MockConfigEntry:
    """Set up the integration with all entities enabled."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    # entities register their variables during setup, the next poll reads them
    await hass.data[DOMAIN][mock_config_entry.entry_id].async_refresh()
    await hass.async_block_till_done()
    return mock_config_entry


@pytest.fixture
async def abus_controller(
    socket_enabled: None,
) -> AsyncGenerator[FakeAbusController]:
    """Return a HIQ controller on a fake A-bus, reached via 127.0.0.1."""
    fake = await start_hiq_controller(NAD)
    with (
        patch(f"{TRANSPORT}.BIND_HOST", "127.0.0.1"),
        patch(f"{TRANSPORT}.LOCAL_PORT", 0),
        patch(f"{TRANSPORT}.CONTROLLER_PORT", fake.port),
        patch(f"{TRANSPORT}.BROADCAST", "127.0.0.1"),
    ):
        yield fake
    fake.close()
