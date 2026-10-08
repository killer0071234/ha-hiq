"""Tests for the HIQ-Home config and options flow."""

from __future__ import annotations

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hiq.const import DOMAIN

from .const import NAD, OPTIONS, TITLE
from .fake_controller import FakeController


async def _start_user_flow(hass: HomeAssistant) -> dict:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


async def test_user_flow(hass: HomeAssistant, controller: FakeController) -> None:
    """Test a controller is added and set up."""
    result = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], OPTIONS)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    entry = result["result"]
    assert entry.options == OPTIONS
    assert entry.data == {}
    assert entry.state is config_entries.ConfigEntryState.LOADED


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, controller: FakeController
) -> None:
    """Test an unreachable SCGI server shows an error and can be retried."""
    controller.online = False
    result = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], OPTIONS)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    controller.online = True
    result = await hass.config_entries.flow.async_configure(result["flow_id"], OPTIONS)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_plc_not_existing(
    hass: HomeAssistant, controller: FakeController
) -> None:
    """Test a controller without a running program is rejected."""
    controller.values[f"c{NAD}.sys.plc_status"] = "pgm missing"
    result = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], OPTIONS)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "plc_not_existing"}


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    controller: FakeController,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the same controller can not be added twice."""
    mock_config_entry.add_to_hass(hass)
    result = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], OPTIONS)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def _options_step(hass: HomeAssistant, entry: MockConfigEntry, step: str) -> dict:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": step}
    )
    assert result["type"] is FlowResultType.FORM
    return result


async def _reload_data(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Wait for the entry reload and read the new variables."""
    await hass.async_block_till_done()
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    await hass.async_block_till_done()


async def _add_sensor(
    hass: HomeAssistant, entry: MockConfigEntry, user_input: dict
) -> None:
    result = await _options_step(hass, entry, "add_sensor")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await _reload_data(hass, entry)


async def _remove_sensor(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    result = await _options_step(hass, entry, "remove_sensor")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"index": ["0"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["sensor"] == []
    await hass.async_block_till_done()


def _custom_entities(hass: HomeAssistant, entry: MockConfigEntry) -> list[str]:
    """Return the entity ids of the custom sensors device."""
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, f"{NAD} custom"), entry.entry_id
    )
    if device is None:
        return []
    return [
        e.entity_id for e in er.async_entries_for_device(er.async_get(hass), device.id)
    ]


async def test_options_flow_custom_sensor(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test adding, editing and removing a custom sensor."""
    entry = init_integration

    # add
    await _add_sensor(
        hass,
        entry,
        {
            "tag": "th00_max_time",
            "name": "Max time",
            "value_template": "{{ value | int * 2 }}",
            "unit_of_measurement": "min",
        },
    )
    assert entry.options["sensor"][0]["tag"] == "th00_max_time"
    [entity_id] = _custom_entities(hass, entry)
    state = hass.states.get(entity_id)
    assert state.state == "120"
    assert state.name.endswith("Max time")
    assert state.attributes["unit_of_measurement"] == "min"

    # edit: name changes, the template is dropped
    result = await _options_step(hass, entry, "select_edit_sensor")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"index": "0"}
    )
    assert result["step_id"] == "edit_sensor"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Activation time"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["sensor"][0]["name"] == "Activation time"
    assert "value_template" not in entry.options["sensor"][0]
    await _reload_data(hass, entry)
    assert _custom_entities(hass, entry) == [entity_id]
    assert hass.states.get(entity_id).state == "60"

    # remove
    await _remove_sensor(hass, entry)
    assert hass.states.get(entity_id) is None


async def test_options_flow_remove_sensor_from_registry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a removed custom sensor is also removed from the entity registry."""
    await _add_sensor(hass, init_integration, {"tag": "th00_max_time"})
    [entity_id] = _custom_entities(hass, init_integration)

    await _remove_sensor(hass, init_integration)

    assert er.async_get(hass).async_get(entity_id) is None


async def test_options_flow_custom_sensor_for_existing_tag(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a custom sensor for a tag that already has an entity is created."""
    await _add_sensor(hass, init_integration, {"tag": "scan_time"})

    [entity_id] = _custom_entities(hass, init_integration)
    assert hass.states.get(entity_id).state == "5"
    assert hass.states.get("sensor.system_c1000_diagnostic_scan_time").state == "5"


@pytest.mark.parametrize(
    ("tag", "value", "device", "migrated"),
    [
        ("th00_max_time", "60", (DOMAIN, f"{NAD} custom"), True),
        ("scan_time", "5", (DOMAIN, NAD), False),
    ],
    ids=["custom_sensor", "built_in_sensor"],
)
async def test_custom_sensor_unique_id_migration(
    hass: HomeAssistant,
    controller: FakeController,
    enable_all_entities: None,
    tag: str,
    value: str,
    device: tuple,
    migrated: bool,
) -> None:
    """Test custom sensors move from the tag to their own unique id.

    Built-in sensors used the same tag as unique id and must not be taken over.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title=TITLE,
        unique_id=TITLE,
        options={
            **OPTIONS,
            "sensor": [{"tag": tag, "name": "Custom", "unique_id": "abc"}],
        },
    )
    entry.add_to_hass(hass)
    device_entry = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={device}
    )
    entity_registry = er.async_get(hass)
    old = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"c{NAD}.{tag}",
        config_entry=entry,
        device_id=device_entry.id,
        suggested_object_id="old_sensor",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await _reload_data(hass, entry)

    custom = entity_registry.async_get_entity_id("sensor", DOMAIN, "abc")
    assert (custom == old.entity_id) is migrated
    assert hass.states.get(custom).state == value
    assert entity_registry.async_get(old.entity_id).unique_id == (
        "abc" if migrated else f"c{NAD}.{tag}"
    )


async def test_options_flow_only_lists_own_variables(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the variable list contains the variables without controller prefix."""
    result = await _options_step(hass, init_integration, "add_sensor")

    options = result["data_schema"].schema["tag"].config["options"]
    assert "scan_time" in options
    assert not [option for option in options if option.startswith(f"c{NAD}.")]
