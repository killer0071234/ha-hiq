"""HIQ controller on a fake A-bus (UDP) for the direct connection tests."""

from __future__ import annotations

from typing import Any

from cybro.testing import FakeAbusController, FakeVar
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hiq.const import DOMAIN

from .const import NAD
from .fake_controller import HIQ_TAGS

# module of the shared socket, its addresses are patched in the tests
TRANSPORT = "custom_components.hiq.transport"


def hiq_variables(tags: dict[str, str]) -> list[FakeVar]:
    """Return the variables of a controller holding the given tags."""
    return [
        FakeVar(name, "real" if "." in value else "int", float(value))
        for name, value in tags.items()
    ]


async def start_hiq_controller(
    nad: int,
    tags: dict[str, str] | None = None,
    host: str = "127.0.0.1",
    port: int = 0,
) -> FakeAbusController:
    """Start a fake HIQ controller (port 0: a random port)."""
    return await FakeAbusController.start(
        nad, hiq_variables(HIQ_TAGS if tags is None else tags), host=host, port=port
    )


def direct_entry(nad: int = NAD, **options: Any) -> MockConfigEntry:
    """Return a config entry of a directly connected controller."""
    options = {
        "address": nad,
        "connection": "direct",
        "ip_address": "127.0.0.1",
        **options,
    }
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        title=f"c{nad}",
        unique_id=f"c{nad}",
        options={key: value for key, value in options.items() if value is not None},
    )
