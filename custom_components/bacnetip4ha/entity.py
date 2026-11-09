"""Entidad base."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import BACnetCoordinator


class BACnetEntity(CoordinatorEntity[BACnetCoordinator]):
    """Entidad ligada a un objeto BACnet de un dispositivo."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BACnetCoordinator, obj: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._obj = obj
        self._object_id: str = obj["id"]
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{self._object_id}"
        self._attr_name = obj.get("name") or self._object_id
        self._attr_device_info = DeviceInfo(
            identifiers={coordinator.device_identifier},
            name=coordinator.config_entry.title,
            manufacturer="BACnet",
            model=f"Device {coordinator.instance}",
        )

    @property
    def value(self) -> Any:
        return (self.coordinator.data or {}).get(self._object_id)

    @property
    def available(self) -> bool:
        return super().available and self.value is not None
