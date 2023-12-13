"""Initializer helpers for HIQ."""
from __future__ import annotations
from collections.abc import Generator
import datetime
from typing import Any
from unittest.mock import Mock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.plugins import (
    enable_custom_integrations,
)  # noqa: F401

from custom_components.hiq.const import DOMAIN
from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.recorder import Recorder
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests import const

# pylint: disable=protected-access, redefined-outer-name


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def teardown():
    """Clean up."""
    patch.stopall()


@pytest.fixture
def entry_data_v1() -> dict[str, Any]:
    """Create data for config entry."""
    return {
        "host": const.HOST,
        "port": const.PORT,
        "address": const.NAD,
        "ignore_general_error": False,
    }


@pytest.fixture
def mock_config_entry_v1(entry_data_v1) -> config_entries.ConfigEntry:
    """Create a mock config entry for HIQ."""

    return MockConfigEntry(
        entry_id=const.CONFIG_ENTRY_ID,
        version=1,
        domain=DOMAIN,
        title=const.CONFIG_TITLE,
        data=entry_data_v1,
        options={},
        pref_disable_new_entities=False,
        pref_disable_polling=False,
        source="user",
        unique_id=const.CONFIG_TITLE,
        disabled_by=None,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None, None, None]:
    """Mock setting up a config entry."""
    with patch("custom_components.hiq.async_setup_entry", return_value=True):
        yield
