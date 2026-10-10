"""Tests for the device info helpers of HIQ-Home."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.hiq.models import module_device_info

MODULE = "c1000.th00"


def _coordinator(**values: str) -> SimpleNamespace:
    """Return a coordinator stand-in holding the given th00_* values."""
    variables = {
        f"{MODULE}_{name}": SimpleNamespace(value=value)
        for name, value in values.items()
    }
    return SimpleNamespace(data=SimpleNamespace(vars=variables))


@pytest.mark.parametrize(
    ("card_id", "model"),
    [
        ("1", "OP-1"),
        ("7", "FC mk2"),
        ("60", "LC-10-IQ"),
        ("63", "BC-5-IQ"),
        ("64", "SC-4-IQ"),
        ("65", "TH-1-IQ"),
        ("66", "TH-2-IQ"),
        ("67", "FC-1-IQ"),
        ("69", "TH-3-IQ"),
        ("70", "TH-1T"),
        ("71", "SC-4T"),
        ("72", "LD-D10-IQ"),
        ("4", "8C"),
        ("54", "SC-4-IO"),
        ("137", "RFMSND"),
        ("208", "TS-H mk2"),
        ("9999", "TH-X-IQ"),
        ("99", "card 99"),
    ],
)
def test_model_from_card_id(card_id: str, model: str) -> None:
    """Test the card id is shown as the module model."""
    coordinator = _coordinator(iex_card_id=card_id, firmware_version="1000")

    assert module_device_info(coordinator, MODULE)["model"] == model


@pytest.mark.parametrize(
    ("firmware", "sw_version"),
    [
        ("32767", "32.7.6.7"),
        ("10000", "10.0.0.0"),
        ("1203", "1.2.0.3"),
        ("1000", "1.0.0.0"),
        ("1", "0.0.0.1"),
    ],
)
def test_sw_version_from_firmware(firmware: str, sw_version: str) -> None:
    """Test the firmware is shown as major.minor.build.release."""
    coordinator = _coordinator(iex_card_id="66", firmware_version=firmware)

    assert module_device_info(coordinator, MODULE)["sw_version"] == sw_version


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"iex_card_id": "0", "firmware_version": "0"},
        {"iex_card_id": "?", "firmware_version": "?"},
        {"iex_card_id": "abc", "firmware_version": "-5"},
    ],
    ids=["not_listed", "zero", "not_readable", "invalid"],
)
def test_both_missing_keeps_defaults(values: dict[str, str]) -> None:
    """Test a module without card id and firmware changes nothing."""
    assert module_device_info(_coordinator(**values), MODULE) == {}


@pytest.mark.parametrize("missing", [None, "0", "?", "abc"])
def test_firmware_missing(missing: str | None) -> None:
    """Test a missing firmware is unknown, the model is still shown."""
    values = {"iex_card_id": "66"}
    if missing is not None:
        values["firmware_version"] = missing

    assert module_device_info(_coordinator(**values), MODULE) == {
        "model": "TH-2-IQ",
        "sw_version": "unknown",
    }


@pytest.mark.parametrize("missing", [None, "0", "?", "abc"])
def test_card_id_missing(missing: str | None) -> None:
    """Test a missing card id is unknown, the firmware is still shown."""
    values = {"firmware_version": "1203"}
    if missing is not None:
        values["iex_card_id"] = missing

    assert module_device_info(_coordinator(**values), MODULE) == {
        "model": "unknown",
        "sw_version": "1.2.0.3",
    }
