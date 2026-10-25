"""Support for HIQ-Home scenes."""

from __future__ import annotations

from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_VARIABLE
from .const import DOMAIN
from .const import LOGGER
from .const import MANUFACTURER
from .const import MANUFACTURER_URL
from .const import SCENE_COUNT
from .coordinator import HiqDataUpdateCoordinator
from .models import HiqEntity

ATTR_ACTIVE = "active"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HIQ-Home scenes based on a config entry."""
    coordinator: HiqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    scenes = find_scenes(coordinator)
    if scenes is not None:
        async_add_entities(scenes)


def scene_status_tags(coordinator: HiqDataUpdateCoordinator) -> list[str]:
    """Return the status tag of every scene, empty if the controller has none.

    eg: c1000.scene_status[0] .. c1000.scene_status[31]
    """
    array = f"c{coordinator.cybro.nad}.scene_status"
    if array not in coordinator.data.plc_info.plc_vars:
        return []
    return [f"{array}[{index}]" for index in range(SCENE_COUNT)]


def scene_device_info(coordinator: HiqDataUpdateCoordinator) -> DeviceInfo:
    """Return the device info of the scenes of a controller, eg: c1000 scenes."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{coordinator.cybro.nad} scenes")},
        manufacturer=MANUFACTURER,
        name=f"c{coordinator.cybro.nad} scenes",
        configuration_url=MANUFACTURER_URL,
        **coordinator.via_device_info,
    )


def defined_scenes(coordinator: HiqDataUpdateCoordinator) -> list[tuple[int, str]]:
    """Return index and status tag of the defined scenes (status is not -1)."""
    res: list[tuple[int, str]] = []
    for index, tag in enumerate(scene_status_tags(coordinator)):
        # read during setup, before the platforms
        status = coordinator.data.vars.get(tag)
        if status is not None and status.value not in ("-1", "?"):
            res.append((index, tag))
    return res


def find_scenes(coordinator: HiqDataUpdateCoordinator) -> list[HiqScene] | None:
    """Find the defined scenes, eg: c1000.scene_status[3]."""
    res = [
        HiqScene(coordinator, index, tag) for index, tag in defined_scenes(coordinator)
    ]
    if len(res) > 0:
        return res
    return None


class HiqScene(HiqEntity, Scene):
    """Defines a scene of lights and blinds of the HIQ controller."""

    _attr_has_entity_name = True
    _attr_translation_key = "scene"

    def __init__(
        self, coordinator: HiqDataUpdateCoordinator, index: int, status_tag: str
    ) -> None:
        """Initialize a HIQ-Home scene."""
        super().__init__(coordinator=coordinator)
        self._index = index
        self._status_tag = status_tag
        self._attr_unique_id = status_tag
        self._attr_translation_placeholders = {"index": str(index)}
        self._attr_device_info = scene_device_info(coordinator)
        coordinator.data.add_var(status_tag, var_type=0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return if the scene is active on the controller."""
        status = self.coordinator.get_value(self._status_tag)
        return {
            ATTR_ACTIVE: status == 1 if isinstance(status, int) else None,
            ATTR_VARIABLE: self._status_tag,
        }

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        tag = f"c{self.coordinator.cybro.nad}.global_scene_request"
        LOGGER.debug("Activate scene %s -> %s", self._index, tag)
        await self.coordinator.cybro.write_var(tag, str(self._index))
        await self.coordinator.async_refresh()
