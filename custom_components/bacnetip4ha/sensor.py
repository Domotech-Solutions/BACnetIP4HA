"""Sensores: analog-input, multi-state-input y objetos Schedule."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import SCHEDULE_TYPE
from .const import DOMAIN, SERVICE_GET_SCHEDULE, SERVICE_SET_WEEKLY_SCHEDULE, UNITS_MAP
from .coordinator import BACnetCoordinator
from .entity import BACnetEntity

DAY_ENTRY = vol.Schema(
    {
        vol.Required("time"): cv.string,  # "HH:MM" o "HH:MM:SS"
        vol.Required("value"): vol.Any(bool, int, float),
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: BACnetCoordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    entities: list[BACnetEntity] = []
    for obj in coordinator.objects:
        otype = obj["id"].split(",")[0]
        if otype == SCHEDULE_TYPE:
            entities.append(BACnetScheduleSensor(coordinator, obj))
        elif otype in ("analog-input", "multi-state-input"):
            entities.append(BACnetSensor(coordinator, obj))
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_GET_SCHEDULE,
        {},
        "async_get_schedule",
        supports_response=SupportsResponse.ONLY,
    )
    platform.async_register_entity_service(
        SERVICE_SET_WEEKLY_SCHEDULE,
        {
            vol.Required("weekly"): vol.All(
                [[DAY_ENTRY]], vol.Length(min=7, max=7)
            ),
        },
        "async_set_weekly_schedule",
    )


class BACnetSensor(BACnetEntity, SensorEntity):
    def __init__(self, coordinator: BACnetCoordinator, obj: dict) -> None:
        super().__init__(coordinator, obj)
        units = obj.get("units")
        if units:
            self._attr_native_unit_of_measurement = UNITS_MAP.get(units, units)
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        value = self.value
        state_text = self._obj.get("state_text")
        if state_text and isinstance(value, (int, float)) and 1 <= int(value) <= len(state_text):
            return state_text[int(value) - 1]
        return value


class BACnetScheduleSensor(BACnetEntity, SensorEntity):
    """Un objeto Schedule: estado = present-value, atributos = horario semanal."""

    _attr_icon = "mdi:calendar-clock"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.schedule(
            self._object_id
        ) is not None

    @property
    def native_value(self):
        sched = self.coordinator.schedule(self._object_id)
        return None if sched is None else sched.present_value

    @property
    def extra_state_attributes(self):
        sched = self.coordinator.schedule(self._object_id)
        if sched is None:
            return None
        return {
            "default": sched.default,
            "weekly": sched.weekly,  # lunes..domingo
            "exception_entries": sched.exception_count,
        }

    async def async_get_schedule(self) -> ServiceResponse:
        sched = await self.coordinator.client.read_schedule(
            self.coordinator.address, self._object_id
        )
        return {
            "present_value": sched.present_value,
            "default": sched.default,
            "weekly": sched.weekly,
            "exception_entries": sched.exception_count,
        }

    async def async_set_weekly_schedule(self, weekly) -> None:
        await self.coordinator.client.write_weekly_schedule(
            self.coordinator.address, self._object_id, weekly
        )
        await self.coordinator.async_request_refresh()
