"""Read-only tests of the integration against a real SCGI server.

Skipped unless a controller is given, e.g.:

    HIQ_LIVE_HOST=192.168.1.10 HIQ_LIVE_NAD=1000 scripts/test tests/live

HIQ_LIVE_PORT defaults to 4000. Nothing is ever written to the controller,
every request with a value fails the test before it is sent.
"""

from __future__ import annotations

import logging
import os
import re
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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hiq.const import DEVICE_SW_VERSION
from custom_components.hiq.const import DOMAIN
from custom_components.hiq.const import IEX_CARD_MODELS

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


async def test_thermostat_device_info(
    hass: HomeAssistant, enable_all_entities: None
) -> None:
    """Test thermostat devices show the card id and firmware of their module."""
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
    thermostats = sorted(
        {
            name.removesuffix("_general_error")
            for name in coordinator.data.plc_info.plc_vars
            if re.fullmatch(rf"c{NAD}\.th\d+_general_error", name)
        }
    )
    if not thermostats:
        pytest.skip("controller has no thermostats")

    def _raw(name: str) -> int:
        """Return a module value read directly from the controller, 0 if missing."""
        try:
            return int(raw[name])
        except KeyError, ValueError:
            return 0

    names = [
        f"{th}_{suffix}"
        for th in thermostats
        for suffix in ("iex_card_id", "firmware_version")
        if f"{th}_{suffix}" in coordinator.data.plc_info.plc_vars
    ]
    raw: dict[str, str] = {}
    if names:
        data = await coordinator.cybro.request(dict.fromkeys(names, ""))
        variables = data["var"] if isinstance(data["var"], list) else [data["var"]]
        raw = {var["name"]: var["value"] for var in variables}

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    checked = []
    for th in thermostats:
        entity_id = entity_registry.async_get_entity_id(
            "climate", DOMAIN, f"{th}_thermostat"
        )
        if entity_id is None:  # thermostat with a general error
            continue
        checked.append(th)
        entity = entity_registry.async_get(entity_id)
        device = device_registry.async_get(entity.device_id)
        card_id = max(_raw(f"{th}_iex_card_id"), 0)
        firmware = max(_raw(f"{th}_firmware_version"), 0)
        if not card_id and not firmware:
            expected = ("HIQ controller", DEVICE_SW_VERSION)
        else:
            expected = (
                IEX_CARD_MODELS.get(card_id, f"card {card_id}")
                if card_id
                else "unknown",
                ".".join(
                    str(part)
                    for part in (
                        firmware // 1000,
                        firmware // 100 % 10,
                        firmware // 10 % 10,
                        firmware % 10,
                    )
                )
                if firmware
                else "unknown",
            )
        assert (device.model, device.sw_version) == expected, th
    assert checked
