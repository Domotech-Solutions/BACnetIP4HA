"""Coordinador de sondeo para un dispositivo BACnet."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import SCHEDULE_TYPE, BACnetClient, ScheduleData
from .const import (
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_INSTANCE,
    CONF_OBJECTS,
    CONF_SCAN_INTERVAL,
    CONF_WRITE_PRIORITY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WRITE_PRIORITY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class BACnetCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Lee los puntos y horarios seleccionados de un dispositivo.

    data = {"analog-value,1": 21.5, "schedule,1": ScheduleData(...), ...}
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: BACnetClient) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.address: str = entry.data[CONF_DEVICE_ADDRESS]
        self.instance: int = entry.data[CONF_DEVICE_INSTANCE]
        self.write_priority: int = entry.options.get(
            CONF_WRITE_PRIORITY, DEFAULT_WRITE_PRIORITY
        )
        # [{"id": "analog-value,1", "name": "...", "units": "...", "state_text": [...]}]
        self.objects: list[dict[str, Any]] = entry.data[CONF_OBJECTS]

    @property
    def device_identifier(self) -> tuple[str, str]:
        return (DOMAIN, f"{self.address}-{self.instance}")

    async def _async_update_data(self) -> dict[str, Any]:
        points = [o["id"] for o in self.objects if not o["id"].startswith(SCHEDULE_TYPE)]
        schedules = [o["id"] for o in self.objects if o["id"].startswith(SCHEDULE_TYPE)]
        data: dict[str, Any] = {}
        try:
            if points:
                data.update(await self.client.read_present_values(self.address, points))
            for sid in schedules:
                data[sid] = await self.client.read_schedule(self.address, sid)
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Error comunicando con {self.address}: {err}") from err
        return data

    def schedule(self, object_id: str) -> ScheduleData | None:
        value = (self.data or {}).get(object_id)
        return value if isinstance(value, ScheduleData) else None
