"""Read-only tests of the integration against a real SCGI server.

Skipped unless a controller is given, e.g.:

    HIQ_LIVE_HOST=192.168.1.10 HIQ_LIVE_NAD=1000 scripts/test tests/live

HIQ_LIVE_PORT defaults to 4000. Nothing is ever written to the controller,
every request with a value fails the test before it is sent.
"""

from __future__ import annotations

import logging
import os
import socket
from collections import Counter
from collections.abc import Generator
from unittest.mock import patch

import cybro.cybro
import pytest
import pytest_socket
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hiq.const import DOMAIN

HOST = os.environ.get("HIQ_LIVE_HOST", "")
PORT = int(os.environ.get("HIQ_LIVE_PORT", "4000"))
NAD = int(os.environ.get("HIQ_LIVE_NAD", "0"))
OPTIONS = {"host": HOST, "port": PORT, "address": NAD}

pytestmark = pytest.mark.skipif(
    not HOST or not NAD, reason="set HIQ_LIVE_HOST and HIQ_LIVE_NAD to run"
)


@pytest.fixture(autouse=True)
def allow_controller_connection(socket_enabled: None) -> None:
    """Allow connections to the SCGI server only."""
    server = HOST.split("//")[-1].split("/")[0]
    pytest_socket.socket_allow_hosts(
        ["127.0.0.1", socket.gethostbyname(server)], allow_unix_socket=True
    )


@pytest.fixture(autouse=True)
def read_only() -> Generator[None]:
    """Fail on any write to the controller, before it is sent."""
    build_query = cybro.cybro._build_query

    def _read_only_query(data: dict | str | None) -> str:
        query = build_query(data)
        if "=" in query:
            raise AssertionError(f"write to the controller attempted: {query}")
        return query

    with patch.object(cybro.cybro, "_build_query", _read_only_query):
        yield


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow accepts the server and controller."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], OPTIONS)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"c{NAD}@{HOST}:{PORT}"


async def test_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_all_entities: None,
) -> None:
    """Test all entities are set up and polled without errors."""
    caplog.set_level(logging.WARNING)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title=f"c{NAD}@{HOST}:{PORT}",
        unique_id=f"c{NAD}@{HOST}:{PORT}",
        data={},
        options=OPTIONS,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][entry.entry_id]
    for _ in range(2):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert coordinator.last_update_success

    entity_ids = [
        e.entity_id
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    ]
    assert entity_ids
    states = [hass.states.get(entity_id) for entity_id in entity_ids]
    assert [s.entity_id for s in states if s.state == STATE_UNAVAILABLE] == []

    # entities without own name are numbered by Home Assistant (e.g. _2)
    names = Counter(s.attributes["friendly_name"] for s in states)
    assert [name for name, count in names.items() if count > 1] == []

    problems = [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.WARNING
        and "has not been tested by Home Assistant" not in record.getMessage()
        # asyncio debug mode reports slow steps, which depends on the network
        and not (
            record.name == "asyncio" and record.getMessage().startswith("Executing")
        )
    ]
    assert problems == []
