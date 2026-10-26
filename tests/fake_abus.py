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

# variables the HIQ program sets at startup (docs/abus-notes.md)
HIQ_PROGRAM = {
    "program_id": "3",
    "version_major": "6",
    "version_minor": "1",
    "version_release": "1",
}


def hiq_variables(tags: dict[str, str]) -> list[FakeVar]:
    """Return the variables of a controller holding the given tags."""
    return [
        FakeVar(name, "real" if "." in value else "int", float(value))
        for name, value in tags.items()
    ]


# variables of socket 1 (HIQ-to-HIQ sync), their types matter
SOCKET_VARS = [
    FakeVar("socket_req", "bit"),
    *(
        FakeVar(name, "int")
        for name in (
            "socket_command",
            "socket_argument_0",
            "socket_argument_1",
            "socket_argument_2",
            "socket_argument_3",
        )
    ),
    FakeVar("socket_from", "long"),
    FakeVar("socket_to", "long"),
]


async def start_hiq_controller(
    nad: int,
    tags: dict[str, str] | None = None,
    host: str = "127.0.0.1",
    port: int = 0,
    extra: list[FakeVar] | None = None,
) -> FakeAbusController:
    """Start a fake HIQ controller (port 0: a random port)."""
    variables = hiq_variables(HIQ_TAGS if tags is None else tags) + (extra or [])
    return await FakeAbusController.start(nad, variables, host=host, port=port)


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
