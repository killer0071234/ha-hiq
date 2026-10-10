"""Tests writing to a real HIQ controller through the entities.

Skipped unless writing is explicitly allowed, e.g.:

    HIQ_LIVE_HOST=192.168.1.10 HIQ_LIVE_NAD=1000 HIQ_LIVE_WRITE=1 \
        scripts/test tests/live

Only lights, blinds, the hvac mode and thermostat th01 are written. Any other
write fails the test before it is sent, and every written tag is set back to
its value from before the test.
"""

from __future__ import annotations

import asyncio
import os
import re
from collections.abc import AsyncGenerator, Callable, Generator
from unittest.mock import patch
from urllib.parse import unquote

import cybro.cybro
import pytest
from homeassistant.components.climate import (
    ATTR_PRESET_MODE,
    PRESET_COMFORT,
    PRESET_ECO,
    HVACMode,
)
from homeassistant.components.cover import ATTR_CURRENT_POSITION, ATTR_POSITION
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hiq import get_write_req_th
from custom_components.hiq.const import DOMAIN
from custom_components.hiq.coordinator import HiqDataUpdateCoordinator

from .test_live import HOST, NAD, OPTIONS, PORT, allow_controller_connection  # noqa: F401

pytestmark = pytest.mark.skipif(
    not HOST or not NAD or os.environ.get("HIQ_LIVE_WRITE") != "1",
    reason="set HIQ_LIVE_HOST, HIQ_LIVE_NAD and HIQ_LIVE_WRITE=1 to run",
)

WRITABLE = re.compile(
    rf"c{NAD}\.("
    r"lc\d+_qx\d+"  # on / off lights
    r"|ld\d+_qw\d+"  # dimmers
    r"|bc\d+_blinds_setpoint_\d+"  # blinds
    r"|hvac_mode"
    r"|th01_\w+"  # thermostat 1 only
    r")"
)

LIGHT = "light.lights_light_c{nad}_lc00_qx00_light"
DIMMER = "light.lights_light_c{nad}_ld00_qw00_light"
BLIND = "cover.blinds_blind_c{nad}_bc00_blinds_position_00_blind"
HVAC_MODE = "select.climate_c{nad}_hvac_operation_mode_hvac"
THERMOSTAT = "climate.climate_c{nad}_th01_thermostat"


def _entity(template: str) -> str:
    return template.format(nad=NAD)


@pytest.fixture
def written() -> Generator[list[str]]:
    """Fail on writes outside WRITABLE before they are sent, record the others."""
    names: list[str] = []
    build_query = cybro.cybro._build_query

    def _guarded_query(data: dict | str | None) -> str:
        query = build_query(data)
        for part in query.split("&"):
            if "=" not in part:
                continue
            name = unquote(part.split("=", 1)[0])
            if not WRITABLE.fullmatch(name):
                raise AssertionError(f"write to a protected tag attempted: {part}")
            names.append(name)
        return query

    with patch.object(cybro.cybro, "_build_query", _guarded_query):
        yield names


@pytest.fixture
async def coordinator(
    hass: HomeAssistant, written: list[str], enable_all_entities: None
) -> AsyncGenerator[HiqDataUpdateCoordinator]:
    """Set up the integration, restore every written tag afterwards."""
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
    coordinator: HiqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    # entities add their tags while they are set up, poll once more to read them
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    before = await _read(
        coordinator,
        [n for n in coordinator.data.plc_info.plc_vars if WRITABLE.fullmatch(n)],
    )

    yield coordinator

    restore: dict[str, str] = {}
    for name in dict.fromkeys(written):
        if name.endswith("_req"):
            continue
        restore[name] = before[name]
        if req := get_write_req_th(name, f"c{NAD}.th01"):
            restore[req] = "1"
    if restore:
        await coordinator.cybro.request(restore)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def _read(
    coordinator: HiqDataUpdateCoordinator, names: list[str]
) -> dict[str, str]:
    """Read tags directly from the controller."""
    data = await coordinator.cybro.request(dict.fromkeys(names, ""))
    variables = data["var"] if isinstance(data["var"], list) else [data["var"]]
    return {var["name"]: var["value"] for var in variables}


async def _wait_for(
    hass: HomeAssistant,
    coordinator: HiqDataUpdateCoordinator,
    entity_id: str,
    check: Callable[[State], bool],
    timeout: float = 10.0,
) -> State:
    """Poll the controller until the state passes check, return the last state."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        if check(state) or loop.time() > deadline:
            return state
        await asyncio.sleep(0.5)


async def test_light_turn_on_off(
    hass: HomeAssistant, coordinator: HiqDataUpdateCoordinator
) -> None:
    """Test an on / off light is switched on and off."""
    light = _entity(LIGHT)

    await hass.services.async_call(
        "light", "turn_on", {ATTR_ENTITY_ID: light}, blocking=True
    )
    state = await _wait_for(hass, coordinator, light, lambda s: s.state == STATE_ON)
    assert state.state == STATE_ON

    await hass.services.async_call(
        "light", "turn_off", {ATTR_ENTITY_ID: light}, blocking=True
    )
    state = await _wait_for(hass, coordinator, light, lambda s: s.state == STATE_OFF)
    assert state.state == STATE_OFF


async def test_dimmer_brightness(
    hass: HomeAssistant, coordinator: HiqDataUpdateCoordinator
) -> None:
    """Test a dimmer is set to a brightness and turned off."""
    dimmer = _entity(DIMMER)

    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: dimmer, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    state = await _wait_for(
        hass, coordinator, dimmer, lambda s: s.attributes.get(ATTR_BRIGHTNESS) == 128
    )
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128

    await hass.services.async_call(
        "light", "turn_off", {ATTR_ENTITY_ID: dimmer}, blocking=True
    )
    state = await _wait_for(hass, coordinator, dimmer, lambda s: s.state == STATE_OFF)
    assert state.state == STATE_OFF


async def test_dimmer_turn_on_without_brightness(
    hass: HomeAssistant, coordinator: HiqDataUpdateCoordinator
) -> None:
    """Test a dimmer turned on without brightness is fully on."""
    dimmer = _entity(DIMMER)
    await hass.services.async_call(
        "light", "turn_off", {ATTR_ENTITY_ID: dimmer}, blocking=True
    )
    await _wait_for(hass, coordinator, dimmer, lambda s: s.state == STATE_OFF)

    await hass.services.async_call(
        "light", "turn_on", {ATTR_ENTITY_ID: dimmer}, blocking=True
    )
    state = await _wait_for(
        hass, coordinator, dimmer, lambda s: s.attributes.get(ATTR_BRIGHTNESS) == 255
    )

    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 255


async def test_blind_set_position(
    hass: HomeAssistant, coordinator: HiqDataUpdateCoordinator
) -> None:
    """Test a blind moves to a position (100 is open)."""
    blind = _entity(BLIND)
    start = hass.states.get(blind).attributes.get(ATTR_CURRENT_POSITION)
    target = 30 if start != 30 else 70

    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {ATTR_ENTITY_ID: blind, ATTR_POSITION: target},
        blocking=True,
    )
    state = await _wait_for(
        hass,
        coordinator,
        blind,
        lambda s: s.attributes.get(ATTR_CURRENT_POSITION) == target,
        timeout=90,
    )

    assert state.attributes.get(ATTR_CURRENT_POSITION) == target


async def test_hvac_mode_sets_thermostat_mode(
    hass: HomeAssistant, coordinator: HiqDataUpdateCoordinator
) -> None:
    """Test the hvac mode select switches the thermostat between heat and cool."""
    hvac_select = _entity(HVAC_MODE)
    thermostat = _entity(THERMOSTAT)
    option, mode = (
        ("cooling", HVACMode.COOL)
        if hass.states.get(hvac_select).state != "cooling"
        else ("heating", HVACMode.HEAT)
    )

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: hvac_select, "option": option},
        blocking=True,
    )
    state = await _wait_for(hass, coordinator, thermostat, lambda s: s.state == mode)

    assert hass.states.get(hvac_select).state == option
    assert state.state == mode
    assert state.attributes["hvac_modes"] == [mode]


async def test_thermostat_preset_mode(
    hass: HomeAssistant, coordinator: HiqDataUpdateCoordinator
) -> None:
    """Test the thermostat is switched between comfort and eco."""
    thermostat = _entity(THERMOSTAT)

    for preset in (PRESET_COMFORT, PRESET_ECO):
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {ATTR_ENTITY_ID: thermostat, ATTR_PRESET_MODE: preset},
            blocking=True,
        )
        state = await _wait_for(
            hass,
            coordinator,
            thermostat,
            lambda s, p=preset: s.attributes.get(ATTR_PRESET_MODE) == p,
        )
        assert state.attributes.get(ATTR_PRESET_MODE) == preset


@pytest.mark.parametrize("preset", [PRESET_COMFORT, PRESET_ECO])
async def test_thermostat_set_temperature(
    hass: HomeAssistant, coordinator: HiqDataUpdateCoordinator, preset: str
) -> None:
    """Test the target temperature of the current preset is changed."""
    thermostat = _entity(THERMOSTAT)
    if preset == PRESET_ECO:
        req = f"c{NAD}.th01_config2_req"
        if (await _read(coordinator, [req]))[req] == "1":
            pytest.skip("thermostat does not process config requests (pending)")
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {ATTR_ENTITY_ID: thermostat, ATTR_PRESET_MODE: preset},
        blocking=True,
    )
    await _wait_for(
        hass,
        coordinator,
        thermostat,
        lambda s: s.attributes.get(ATTR_PRESET_MODE) == preset,
    )
    current = hass.states.get(thermostat).attributes.get(ATTR_TEMPERATURE)
    target = 18.5 if current != 18.5 else 19.5

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: thermostat, ATTR_TEMPERATURE: target},
        blocking=True,
    )
    state = await _wait_for(
        hass,
        coordinator,
        thermostat,
        lambda s: s.attributes.get(ATTR_TEMPERATURE) == target,
    )

    assert state.attributes.get(ATTR_TEMPERATURE) == target
    assert state.attributes.get(ATTR_PRESET_MODE) == preset
