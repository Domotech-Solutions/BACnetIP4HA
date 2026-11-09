"""Números: analog-value/output y multi-state-value/output (escritura con prioridad)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, UNITS_MAP
from .coordinator import BACnetCoordinator
from .entity import BACnetEntity

PREFIXES = ("analog-value,", "analog-output,", "multi-state-value,", "multi-state-output,")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: BACnetCoordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    async_add_entities(
        BACnetNumber(coordinator, o) for o in coordinator.objects if o["id"].startswith(PREFIXES)
    )


class BACnetNumber(BACnetEntity, NumberEntity):
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = -1_000_000
    _attr_native_max_value = 1_000_000

    def __init__(self, coordinator: BACnetCoordinator, obj: dict) -> None:
        super().__init__(coordinator, obj)
        if obj["id"].startswith("multi-state"):
            self._attr_native_step = 1
            self._attr_native_min_value = 1
            if obj.get("state_text"):
                self._attr_native_max_value = len(obj["state_text"])
        else:
            self._attr_native_step = 0.1
        units = obj.get("units")
        if units:
            self._attr_native_unit_of_measurement = UNITS_MAP.get(units, units)

    @property
    def native_value(self) -> float | None:
        return self.value

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.write_present_value(
            self.coordinator.address,
            self._object_id,
            value,
            priority=self.coordinator.write_priority,
        )
        await self.coordinator.async_request_refresh()
