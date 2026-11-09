"""Interruptores: binary-value y binary-output (escritura con prioridad)."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
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
        BACnetSwitch(coordinator, o)
        for o in coordinator.objects
        if o["id"].startswith(("binary-value,", "binary-output,"))
    )


class BACnetSwitch(BACnetEntity, SwitchEntity):
    @property
    def is_on(self) -> bool | None:
        return self.value

    async def _write(self, value: bool | None) -> None:
        await self.coordinator.client.write_present_value(
            self.coordinator.address,
            self._object_id,
            value,
            priority=self.coordinator.write_priority,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        await self._write(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._write(False)
