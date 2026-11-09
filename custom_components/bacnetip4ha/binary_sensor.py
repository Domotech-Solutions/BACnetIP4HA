"""Sensores binarios: binary-input."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import BACnetCoordinator
from .entity import BACnetEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: BACnetCoordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    async_add_entities(
        BACnetBinarySensor(coordinator, o)
        for o in coordinator.objects
        if o["id"].startswith("binary-input,")
    )


class BACnetBinarySensor(BACnetEntity, BinarySensorEntity):
    @property
    def is_on(self) -> bool | None:
        return self.value
