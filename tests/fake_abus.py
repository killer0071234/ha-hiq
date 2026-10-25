"""HIQ controller on a fake A-bus (UDP) for the direct connection tests."""

from __future__ import annotations

from cybro.testing import FakeAbusController, FakeVar

from .fake_controller import HIQ_TAGS


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
