"""Consistency checks between code, translations, services and requirements."""

from __future__ import annotations

import json
import re
from pathlib import Path
from string import Formatter

import pytest
import yaml
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hiq.const import DOMAIN

ROOT = Path(__file__).parent.parent
INTEGRATION = ROOT / "custom_components" / DOMAIN
LANGUAGES = ("en", "de")


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _translation(language: str) -> dict:
    return _json(INTEGRATION / "translations" / f"{language}.json")


def _flatten(data: dict, prefix: str = "") -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result |= _flatten(value, f"{prefix}{key}.")
        else:
            result[f"{prefix}{key}"] = value
    return result


def _placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(text) if name}


async def test_entities_have_translated_names(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test every entity has a name in all languages.

    Without translation, Home Assistant falls back to the device class name.
    """
    entries = er.async_entries_for_config_entry(
        er.async_get(hass), init_integration.entry_id
    )
    assert entries

    for language in LANGUAGES:
        names = _translation(language)["entity"]
        missing = sorted(
            e.entity_id
            for e in entries
            if e.translation_key
            and "name" not in names.get(e.domain, {}).get(e.translation_key, {})
            and not e.original_device_class
        )
        assert missing == [], f"missing in {language}.json: {missing}"


@pytest.mark.parametrize("language", [lang for lang in LANGUAGES if lang != "en"])
def test_translation_has_no_unknown_keys(language: str) -> None:
    """Test translations contain no keys English does not have (stale keys)."""
    english = _flatten(_translation("en"))
    other = _flatten(_translation(language))

    assert sorted(set(other) - set(english)) == []


@pytest.mark.parametrize("language", [lang for lang in LANGUAGES if lang != "en"])
def test_translation_complete(language: str) -> None:
    """Test entity names and config flow texts are translated."""
    english = _flatten(_translation("en"))
    other = _flatten(_translation(language))

    missing = [
        key
        for key in english
        if key.startswith(("entity.", "config.", "options.", "services."))
        and key not in other
    ]
    assert missing == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_translation_placeholders(language: str) -> None:
    """Test translations use the same placeholders as English."""
    english = _flatten(_translation("en"))
    other = _flatten(_translation(language))

    assert {
        key: _placeholders(text)
        for key, text in other.items()
        if _placeholders(text) != _placeholders(english[key])
    } == {}


@pytest.mark.parametrize("language", LANGUAGES)
def test_flow_steps_described(language: str) -> None:
    """Test every flow step has a description and every field a help text."""
    translation = _translation(language)
    steps = {
        f"{flow}.{name}": step
        for flow in ("config", "options")
        for name, step in translation[flow]["step"].items()
    }

    assert sorted(key for key, step in steps.items() if "description" not in step) == []
    assert (
        sorted(
            f"{key}.{field}"
            for key, step in steps.items()
            for field in step.get("data", {})
            if field not in step.get("data_description", {})
        )
        == []
    )


@pytest.mark.parametrize("language", LANGUAGES)
def test_flow_errors_translated(language: str) -> None:
    """Test every error of the config flow has a text."""
    source = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    errors = set(re.findall(r'SchemaFlowError\("(\w+)"\)', source))

    assert errors
    assert sorted(errors - set(_translation(language)["config"]["error"])) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_flow_abort_translated(language: str) -> None:
    """Test the abort reason of the config flow has a text."""
    assert "already_configured" in _translation(language)["config"].get("abort", {})


def test_strings_match_english() -> None:
    """Test strings.json and translations/en.json have the same keys."""
    strings = _flatten(_json(INTEGRATION / "strings.json"))
    english = _flatten(_translation("en"))

    assert sorted(set(strings) ^ set(english)) == []


def test_strings_equal_english() -> None:
    """Test strings.json holds the same texts as translations/en.json.

    Custom integrations don't resolve [%key:...%] references, so the English
    texts are kept as plain text in both files.
    """
    assert _json(INTEGRATION / "strings.json") == _translation("en")


@pytest.mark.parametrize("language", LANGUAGES)
def test_translation_has_no_references(language: str) -> None:
    """Test translations contain no unresolved [%key:...%] references."""
    references = {
        key: text
        for key, text in _flatten(_translation(language)).items()
        if "[%key:" in text
    }

    assert references == {}


async def test_services_documented(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test services.yaml describes exactly the registered services."""
    documented = yaml.safe_load(
        (INTEGRATION / "services.yaml").read_text(encoding="utf-8")
    )

    assert set(documented) == set(hass.services.async_services_for_domain(DOMAIN))


def _services_yaml() -> dict:
    return yaml.safe_load((INTEGRATION / "services.yaml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("language", LANGUAGES)
def test_services_translated(language: str) -> None:
    """Test every service and field has a name and a description."""
    services = _translation(language).get("services", {})

    missing = [
        f"{service}.{key}"
        for service, definition in _services_yaml().items()
        for key in (
            "name",
            "description",
            *(
                f"fields.{field}.{text}"
                for field in definition.get("fields", {})
                for text in ("name", "description")
            ),
        )
        if key not in _flatten(services.get(service, {}))
    ]
    assert missing == []
    assert sorted(set(services) - set(_services_yaml())) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_service_names_unique(language: str) -> None:
    """Test no two services share a name."""
    names = [s["name"] for s in _translation(language).get("services", {}).values()]

    assert len(names) == len(set(names))


def test_services_yaml_names_unique() -> None:
    """Test no two services share a name in services.yaml (fallback texts)."""
    names = [s["name"] for s in _services_yaml().values()]

    assert len(names) == len(set(names))


def test_write_tag_value_selector() -> None:
    """Test the write_tag value field allows 32-bit and decimal values."""
    selector = _services_yaml()["write_tag"]["fields"]["value"]["selector"]["number"]

    assert selector["min"] <= -(2**31)
    assert selector["max"] >= 2**31 - 1
    assert selector["step"] == "any"


def test_requirements_pinned_for_tests() -> None:
    """Test the tests run with the requirements of manifest.json."""
    manifest = _json(INTEGRATION / "manifest.json")
    test_requirements = {
        line.strip()
        for line in (ROOT / "requirements_test.txt").read_text().splitlines()
    }

    assert sorted(set(manifest["requirements"]) - test_requirements) == []


def test_homeassistant_versions_match() -> None:
    """Test requirements.txt and the test plugin use the same Home Assistant."""
    from importlib.metadata import requires, version

    pinned = re.search(
        r"^homeassistant==(\S+)$",
        (ROOT / "requirements.txt").read_text(),
        re.MULTILINE,
    ).group(1)
    plugin = {
        req.split("==")[1]
        for req in requires("pytest-homeassistant-custom-component")
        if req.startswith("homeassistant==")
    }

    assert plugin == {pinned}
    assert version("homeassistant") == pinned


def test_iot_class_polling() -> None:
    """Test the manifest declares polling, as the coordinator polls the server."""
    assert _json(INTEGRATION / "manifest.json")["iot_class"] == "local_polling"
