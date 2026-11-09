"""Config flow: red -> dispositivo (Who-Is o manual) -> objetos."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components import network
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .client import BACnetClient
from .const import (
    CONF_BBMD,
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_INSTANCE,
    CONF_LOCAL_ADDRESS,
    CONF_OBJECTS,
    CONF_SCAN_INTERVAL,
    CONF_WRITE_PRIORITY,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WRITE_PRIORITY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

MANUAL = "manual"


class BACnetConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._local_address = ""
        self._bbmd: str | None = None
        self._found: dict[str, dict[str, Any]] = {}
        self._device: dict[str, Any] = {}
        self._objects: list[dict[str, Any]] = []
        self._temp_client: BACnetClient | None = None

    # ------------------------------------------------------------ utilidades
    async def _client(self) -> BACnetClient:
        shared = self.hass.data.get(DOMAIN, {}).get("client")
        if shared is not None:
            return shared
        if self._temp_client is None:
            self._temp_client = BACnetClient()
            await self._temp_client.start(self._local_address, bbmd=self._bbmd)
        return self._temp_client

    def _close_temp(self) -> None:
        if self._temp_client is not None:
            self._temp_client.close()
            self._temp_client = None

    # ------------------------------------------------------------------ pasos
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._local_address = user_input[CONF_LOCAL_ADDRESS].strip()
            self._bbmd = (user_input.get(CONF_BBMD) or "").strip() or None
            try:
                client = await self._client()
                devices = await client.discover()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error iniciando BACnet en %s", self._local_address)
                self._close_temp()
                errors["base"] = "cannot_bind"
            else:
                self._found = {
                    f"{d.address}|{d.instance}": {"address": d.address, "instance": d.instance}
                    for d in devices
                }
                return await self.async_step_device()

        source_ip = await network.async_get_source_ip(self.hass)
        default_local = f"{source_ip}/24:{DEFAULT_PORT}"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOCAL_ADDRESS, default=default_local): str,
                    vol.Optional(CONF_BBMD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_device(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            choice = user_input["device"]
            if choice == MANUAL:
                return await self.async_step_manual()
            self._device = dict(self._found[choice])
            return await self._load_objects()

        options = {k: f"Device {v['instance']} — {v['address']}" for k, v in self._found.items()}
        options[MANUAL] = "Manual (IP y device instance)"
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema({vol.Required("device"): vol.In(options)}),
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._device = {
                "address": user_input[CONF_DEVICE_ADDRESS].strip(),
                "instance": int(user_input[CONF_DEVICE_INSTANCE]),
            }
            return await self._load_objects()
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ADDRESS): str,
                    vol.Required(CONF_DEVICE_INSTANCE): vol.All(int, vol.Range(min=0, max=4194302)),
                }
            ),
        )

    async def _load_objects(self) -> ConfigFlowResult:
        client = await self._client()
        try:
            objs = await client.list_objects(self._device["address"], self._device["instance"])
            self._device["name"] = await client.read_device_name(
                self._device["address"], self._device["instance"]
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("No se pudo leer object-list de %s", self._device)
            self._close_temp()
            return self.async_show_form(
                step_id="manual",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_DEVICE_ADDRESS, default=self._device["address"]): str,
                        vol.Required(CONF_DEVICE_INSTANCE, default=self._device["instance"]): int,
                    }
                ),
                errors={"base": "cannot_connect"},
            )
        self._objects = [
            {
                "id": o.identifier,
                "name": o.name or o.identifier,
                "units": o.units,
                "state_text": o.state_text,
            }
            for o in objs
        ]
        return await self.async_step_objects()

    async def async_step_objects(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            selected = set(user_input[CONF_OBJECTS])
            chosen = [o for o in self._objects if o["id"] in selected]
            self._close_temp()

            unique = f"{self._device['address']}-{self._device['instance']}"
            await self.async_set_unique_id(unique)
            self._abort_if_unique_id_configured()
            title = self._device.get("name") or f"BACnet {self._device['instance']}"
            return self.async_create_entry(
                title=title,
                data={
                    CONF_LOCAL_ADDRESS: self._local_address,
                    CONF_BBMD: self._bbmd,
                    CONF_DEVICE_ADDRESS: self._device["address"],
                    CONF_DEVICE_INSTANCE: self._device["instance"],
                    CONF_OBJECTS: chosen,
                },
            )

        choices = {o["id"]: f"{o['name']} ({o['id']})" for o in self._objects}
        return self.async_show_form(
            step_id="objects",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OBJECTS, default=list(choices)): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[{"value": k, "label": v} for k, v in choices.items()],
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return BACnetOptionsFlow()


class BACnetOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(int, vol.Range(min=5, max=3600)),
                    vol.Required(
                        CONF_WRITE_PRIORITY,
                        default=opts.get(CONF_WRITE_PRIORITY, DEFAULT_WRITE_PRIORITY),
                    ): vol.All(int, vol.Range(min=1, max=16)),
                }
            ),
        )
