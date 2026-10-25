"""Tests for HIQ-Home lights."""

from __future__ import annotations

import pytest
from homeassistant.components.light import ColorMode
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.hiq.const import DEVICE_SW_VERSION

from .common import call_service, refresh, setup_with_tags
from .fake_controller import FakeController

ONOFF = "light.lights_light_c1000_lc00_qx00_light"
DIMMER = "light.lights_light_c1000_ld01_qw00_light"
RGB = "light.lights_light_c1000_ld00_qw00_light"


async def test_lights_found(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test lights are created only for modules without a general error."""
    assert sorted(hass.states.async_entity_ids("light")) == sorted([ONOFF, DIMMER, RGB])


async def test_onoff_light(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test a switched light output."""
    state = hass.states.get(ONOFF)
    assert state.state == "on"
    assert state.attributes["color_mode"] == ColorMode.ONOFF
    assert state.attributes["supported_color_modes"] == [ColorMode.ONOFF]
    assert state.attributes["variable"] == "c1000.lc00_qx00"
    assert state.attributes["description"] == "Description of c1000.lc00_qx00"

    await call_service(hass, "light", "turn_off", ONOFF)
    assert controller.written("c1000.lc00_qx00") == ["0"]
    assert hass.states.get(ONOFF).state == "off"

    await call_service(hass, "light", "turn_on", ONOFF)
    assert controller.written("c1000.lc00_qx00") == ["0", "1"]
    assert hass.states.get(ONOFF).state == "on"


async def test_dimmable_light(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test a dimmer output, brightness is a percentage on the controller."""
    state = hass.states.get(DIMMER)
    assert state.state == "on"
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["brightness"] == 102  # 40 %

    await call_service(hass, "light", "turn_on", DIMMER)
    assert controller.written("c1000.ld01_qw00") == ["100"]

    await call_service(hass, "light", "turn_off", DIMMER)
    assert controller.written("c1000.ld01_qw00")[-1] == "0"
    assert hass.states.get(DIMMER).state == "off"


@pytest.mark.parametrize(
    ("brightness", "percent"),
    [(255, "100"), (128, "50"), (64, "25"), (3, "1"), (1, "1")],
)
async def test_dimmable_light_brightness(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
    brightness: int,
    percent: str,
) -> None:
    """Test brightness is written as whole percent, never 0 when turning on."""
    await call_service(hass, "light", "turn_on", DIMMER, brightness=brightness)

    assert controller.written("c1000.ld01_qw00") == [percent]
    assert hass.states.get(DIMMER).state == "on"


@pytest.mark.parametrize("brightness", [26, 77, 128, 179, 230])
async def test_dimmable_light_keeps_brightness(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
    brightness: int,
) -> None:
    """Test a brightness of a whole percent is reported back unchanged."""
    await call_service(hass, "light", "turn_on", DIMMER, brightness=brightness)

    assert hass.states.get(DIMMER).attributes["brightness"] == brightness


async def test_rgb_light(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test an rgb light, hue is stored as 0..100 on the controller."""
    state = hass.states.get(RGB)
    assert state.attributes["color_mode"] == ColorMode.HS
    assert state.attributes["supported_color_modes"] == [ColorMode.HS]
    assert state.attributes["brightness"] == 128  # 50 %

    await call_service(hass, "light", "turn_on", RGB, hs_color=(120, 50))

    assert controller.written("c1000.ld00_qw01") == ["33"]
    assert controller.written("c1000.ld00_qw02") == ["50"]
    assert controller.written("c1000.ld00_qw00") == []


async def test_light_state_changes_on_controller(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test changes made on the controller are picked up by polling."""
    controller.values["c1000.lc00_qx00"] = "0"
    controller.values["c1000.ld01_qw00"] = "0"
    await refresh(hass, init_integration)

    assert hass.states.get(ONOFF).state == "off"
    assert hass.states.get(DIMMER).state == "off"


async def test_dimmable_light_full_brightness(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test 100 % on the controller is reported as full brightness."""
    controller.values["c1000.ld01_qw00"] = "100"
    await refresh(hass, init_integration)

    assert hass.states.get(DIMMER).attributes["brightness"] == 255


async def test_rgb_light_reports_color(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the color of an rgb light is read from the controller."""
    assert tuple(hass.states.get(RGB).attributes["hs_color"]) == (180, 80)


async def test_rgb_light_unknown_color(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test an unknown hue on the controller results in no color."""
    controller.values["c1000.ld00_qw01"] = "?"
    await refresh(hass, init_integration)

    assert hass.states.get(RGB).attributes["hs_color"] is None


async def test_dimmable_light_unknown_brightness(
    hass: HomeAssistant,
    controller: FakeController,
    init_integration: MockConfigEntry,
) -> None:
    """Test an unknown dimmer value results in an unknown light."""
    controller.values["c1000.ld01_qw00"] = "?"
    await refresh(hass, init_integration)

    state = hass.states.get(DIMMER)
    assert state.state == "unknown"
    assert state.attributes.get("brightness") is None


async def test_second_rgb_channel(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test the second rgb channel uses qw05 / qw06 for hue and saturation."""
    controller = await setup_with_tags(
        hass,
        aioclient_mock,
        mock_config_entry,
        {
            "ld02_general_error": "0",
            "ld02_rgb_mode_2": "1",
            "ld02_qw04": "50",
            "ld02_qw05": "25",
            "ld02_qw06": "70",
            "ld02_qw07": "0",
        },
    )
    entity_id = "light.lights_light_c1000_ld02_qw04_light"

    assert hass.states.async_entity_ids("light") == [entity_id]
    state = hass.states.get(entity_id)
    assert state.attributes["color_mode"] == ColorMode.HS
    assert tuple(state.attributes["hs_color"]) == (90, 70)

    await call_service(hass, "light", "turn_on", entity_id, hs_color=(180, 40))

    assert controller.written("c1000.ld02_qw05") == ["50"]
    assert controller.written("c1000.ld02_qw06") == ["40"]


@pytest.mark.parametrize(
    "tags",
    [
        # no rgb mode variable on the module
        {"ld03_general_error": "0", "ld03_qw00": "40"},
        # output outside of the rgb channels
        {"ld03_general_error": "0", "ld03_rgb_mode": "1", "ld03_qw08": "40"},
    ],
    ids=["no_rgb_mode", "not_an_rgb_output"],
)
async def test_dimmable_light_without_rgb(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
    tags: dict[str, str],
) -> None:
    """Test dimmer outputs that can not be rgb are plain dimmable lights."""
    await setup_with_tags(hass, aioclient_mock, mock_config_entry, tags)

    (entity_id,) = hass.states.async_entity_ids("light")
    state = hass.states.get(entity_id)
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["brightness"] == 102


@pytest.mark.parametrize(
    ("tags", "color_mode"),
    [
        ({"ld10_qw00": "40", "ld10_rgb_mode": "1"}, ColorMode.HS),
        ({"ld10_qw00": "40", "ld10_rgb_mode": "0"}, ColorMode.BRIGHTNESS),
        ({"ld10_qw00": "40"}, ColorMode.BRIGHTNESS),
    ],
    ids=["rgb", "not_rgb", "no_rgb_mode"],
)
async def test_light_on_module_not_polled_by_default(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    tags: dict[str, str],
    color_mode: ColorMode,
) -> None:
    """Test the rgb mode is read for modules beyond ld09.

    The cybro library polls the rgb mode of modules ld00 .. ld09 only.
    """
    await setup_with_tags(
        hass,
        aioclient_mock,
        mock_config_entry,
        {"ld10_general_error": "0", "ld10_qw01": "0", "ld10_qw02": "0"} | tags,
    )

    state = hass.states.get("light.lights_light_c1000_ld10_qw00_light")
    assert state.attributes["supported_color_modes"] == [color_mode]


@pytest.mark.parametrize(
    ("entity_id", "model", "sw_version"),
    [
        (ONOFF, "LC-10-IQ", "1.2.0.3"),
        (DIMMER, "LD-D10-IQ", "2.0.0.1"),
        # module without card id and firmware
        (RGB, "HIQ controller", DEVICE_SW_VERSION),
    ],
)
async def test_light_device_shows_module(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_id: str,
    model: str,
    sw_version: str,
) -> None:
    """Test a light device shows the model and firmware of its module."""
    entry = er.async_get(hass).async_get(entity_id)
    device = dr.async_get(hass).async_get(entry.device_id)

    assert (device.model, device.sw_version, device.hw_version) == (
        model,
        sw_version,
        "2/3",
    )


async def test_light_devices_of_one_module(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test every output of a module shows the same module info."""
    await setup_with_tags(
        hass,
        aioclient_mock,
        mock_config_entry,
        {
            "lc00_general_error": "0",
            "lc00_iex_card_id": "60",
            "lc00_firmware_version": "1203",
            "lc00_qx00": "0",
            "lc00_qx01": "0",
        },
    )

    devices = [
        dr.async_get(hass).async_get(er.async_get(hass).async_get(e).device_id)
        for e in hass.states.async_entity_ids("light")
    ]
    assert len(devices) == 2
    assert {(d.model, d.sw_version) for d in devices} == {("LC-10-IQ", "1.2.0.3")}


async def test_no_lights(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test a controller without light outputs has no lights."""
    await setup_with_tags(hass, aioclient_mock, mock_config_entry, {})

    assert hass.states.async_entity_ids("light") == []


# LD-D10: color mode per output, color written through shared registers
D10_TAGS = {
    "ld05_general_error": "0",
    "ld05_qw00": "40",
    "ld05_qw01": "60",
    "ld05_qw02": "80",
    "ld05_color_mode_00": "0",
    "ld05_color_mode_01": "1",
    "ld05_color_mode_02": "2",
    "ld05_rgb_index": "0",
    "ld05_rgb_hue": "0",
    "ld05_rgb_saturation": "0",
    "ld05_rgb_req": "0",
}
D10_DIMMER = "light.lights_light_c1000_ld05_qw00_light"
D10_RGB = "light.lights_light_c1000_ld05_qw01_light"
D10_WHITE = "light.lights_light_c1000_ld05_qw02_light"


async def _setup_d10(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> FakeController:
    """Set up a controller with an LD-D10 module."""
    return await setup_with_tags(hass, aioclient_mock, mock_config_entry, D10_TAGS)


async def test_d10_color_modes(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test every LD-D10 output is a light with its own color mode."""
    await _setup_d10(hass, aioclient_mock, mock_config_entry)

    assert sorted(hass.states.async_entity_ids("light")) == sorted(
        [D10_DIMMER, D10_RGB, D10_WHITE]
    )
    for entity_id, mode in (
        (D10_DIMMER, ColorMode.BRIGHTNESS),
        (D10_RGB, ColorMode.HS),
        (D10_WHITE, ColorMode.COLOR_TEMP),
    ):
        state = hass.states.get(entity_id)
        assert state.attributes["color_mode"] == mode
        assert state.attributes["supported_color_modes"] == [mode]
    white = hass.states.get(D10_WHITE)
    assert white.attributes["min_color_temp_kelvin"] == 2700
    assert white.attributes["max_color_temp_kelvin"] == 6500
    # the color can not be read from the module
    assert hass.states.get(D10_RGB).attributes["hs_color"] is None


async def test_d10_write_rgb(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test the color of an output is written with its index and a request."""
    controller = await _setup_d10(hass, aioclient_mock, mock_config_entry)

    await call_service(hass, "light", "turn_on", D10_RGB, hs_color=(120, 50))

    assert controller.writes[-4:] == [
        ("c1000.ld05_rgb_index", "1"),
        ("c1000.ld05_rgb_hue", "33"),
        ("c1000.ld05_rgb_saturation", "50"),
        ("c1000.ld05_rgb_req", "1"),
    ]
    assert controller.written("c1000.ld05_qw01") == []
    assert tuple(hass.states.get(D10_RGB).attributes["hs_color"]) == (120, 50)


@pytest.mark.parametrize(
    ("kelvin", "percent"),
    [(2700, "0"), (4600, "50"), (6500, "100")],
)
async def test_d10_write_white_temperature(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
    kelvin: int,
    percent: str,
) -> None:
    """Test the white temperature is written as 0..100 % into the hue."""
    controller = await _setup_d10(hass, aioclient_mock, mock_config_entry)

    await call_service(hass, "light", "turn_on", D10_WHITE, color_temp_kelvin=kelvin)

    assert controller.writes[-3:] == [
        ("c1000.ld05_rgb_index", "2"),
        ("c1000.ld05_rgb_hue", percent),
        ("c1000.ld05_rgb_req", "1"),
    ]
    assert hass.states.get(D10_WHITE).attributes["color_temp_kelvin"] == kelvin


async def test_d10_write_color_and_brightness(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test brightness is still written to the output with a color."""
    controller = await _setup_d10(hass, aioclient_mock, mock_config_entry)

    await call_service(
        hass, "light", "turn_on", D10_RGB, hs_color=(180, 40), brightness=255
    )

    assert controller.written("c1000.ld05_rgb_hue") == ["50"]
    assert controller.written("c1000.ld05_qw01") == ["100"]


async def test_d10_brightness_and_off(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test brightness and off without a color only use the output."""
    controller = await _setup_d10(hass, aioclient_mock, mock_config_entry)

    await call_service(hass, "light", "turn_on", D10_RGB, brightness=128)
    await call_service(hass, "light", "turn_off", D10_RGB)

    assert controller.written("c1000.ld05_qw01") == ["50", "0"]
    assert controller.written("c1000.ld05_rgb_req") == []


async def test_d10_restores_color(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    enable_all_entities: None,
) -> None:
    """Test the last written color is restored after a restart."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(D10_RGB, "off"),
                {"hs_color": [240.0, 30.0], "color_temp_kelvin": None},
            ),
            (
                State(D10_WHITE, "off"),
                {"hs_color": None, "color_temp_kelvin": 3000},
            ),
        ],
    )
    await _setup_d10(hass, aioclient_mock, mock_config_entry)

    assert tuple(hass.states.get(D10_RGB).attributes["hs_color"]) == (240, 30)
    assert hass.states.get(D10_WHITE).attributes["color_temp_kelvin"] == 3000
