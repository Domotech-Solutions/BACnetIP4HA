"""Integración BACnet/IP para Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .client import BACnetClient
from .const import CONF_BBMD, CONF_LOCAL_ADDRESS, DOMAIN
from .coordinator import BACnetCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
]


async def _async_get_client(hass: HomeAssistant, entry: ConfigEntry) -> BACnetClient:
    """Un único socket BACnet (puerto UDP 47808) compartido por todas las entradas."""
    data = hass.data.setdefault(DOMAIN, {"client": None, "users": 0, "coordinators": {}})
    if data["client"] is None:
        client = BACnetClient()
        await client.start(
            entry.data[CONF_LOCAL_ADDRESS],
            bbmd=entry.data.get(CONF_BBMD) or None,
        )
        data["client"] = client
    data["users"] += 1
    return data["client"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = await _async_get_client(hass, entry)
    coordinator = BACnetCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        _release_client(hass)
        raise

    hass.data[DOMAIN]["coordinators"][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _release_client(hass: HomeAssistant) -> None:
    data = hass.data[DOMAIN]
    data["users"] -= 1
    if data["users"] <= 0 and data["client"] is not None:
        data["client"].close()
        data["client"] = None
        data["users"] = 0


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN]["coordinators"].pop(entry.entry_id, None)
        _release_client(hass)
    return unloaded
