"""Cliente BACnet/IP asyncio (bacpypes3) independiente de Home Assistant.

Todo lo que toca bacpypes3 vive aquí para poder probarlo sin arrancar HA.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.basetypes import DailySchedule, ErrorType, TimeValue
from bacpypes3.constructeddata import AnyAtomic
from bacpypes3.pdu import Address
from bacpypes3.primitivedata import (
    Boolean,
    CharacterString,
    Enumerated,
    Integer,
    Null,
    ObjectIdentifier,
    Real,
    Time,
    Unsigned,
)

_LOGGER = logging.getLogger(__name__)

# Tipos de objeto que se exponen como puntos "simples" (present-value).
POINT_TYPES = {
    "analog-input",
    "analog-output",
    "analog-value",
    "binary-input",
    "binary-output",
    "binary-value",
    "multi-state-input",
    "multi-state-output",
    "multi-state-value",
}
SCHEDULE_TYPE = "schedule"
CALENDAR_TYPE = "calendar"
WRITABLE_TYPES = {
    "analog-output",
    "analog-value",
    "binary-output",
    "binary-value",
    "multi-state-output",
    "multi-state-value",
}

RPM_CHUNK = 20  # objetos por petición ReadPropertyMultiple


@dataclass
class BACnetDevice:
    """Dispositivo descubierto por Who-Is / I-Am."""

    instance: int
    address: str
    vendor_id: int | None = None
    name: str | None = None


@dataclass
class BACnetObject:
    """Objeto BACnet de un dispositivo."""

    object_type: str
    instance: int
    name: str | None = None
    description: str | None = None
    units: str | None = None
    state_text: list[str] | None = None

    @property
    def identifier(self) -> str:
        return f"{self.object_type},{self.instance}"


@dataclass
class ScheduleData:
    """Contenido de un objeto Schedule en formato serializable (JSON)."""

    present_value: Any = None
    default: Any = None
    # 7 listas (lunes..domingo) de {"time": "HH:MM:SS", "value": x}
    weekly: list[list[dict[str, Any]]] = field(default_factory=list)
    exception_count: int = 0


def _is_error(value: Any) -> bool:
    """RPM devuelve ErrorType (no excepción) por propiedad fallida."""
    return isinstance(value, (Exception, ErrorType))


def _to_python(value: Any) -> Any:
    """Convierte un valor bacpypes3 a un tipo nativo serializable."""
    if isinstance(value, AnyAtomic):
        value = value.get_value()
    if value is None or isinstance(value, Null):
        return None
    if isinstance(value, Boolean):
        return bool(value)
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enumerated):
        return str(value)
    if isinstance(value, Time):
        return "%02d:%02d:%02d" % value[:3]
    return str(value)


def _normalize_value(value: Any) -> Any:
    """present-value -> valor nativo (bool para binarios, str para enumerados)."""
    py = _to_python(value)
    if isinstance(py, str):
        if py == "active":
            return True
        if py == "inactive":
            return False
    return py


class BACnetClient:
    """Envoltorio asyncio sobre bacpypes3."""

    def __init__(self) -> None:
        self._app: Application | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ ciclo
    async def start(
        self,
        local_address: str,
        device_instance: int = 599,
        device_name: str = "BACnetIP4HA",
        bbmd: str | None = None,
        bbmd_ttl: int = 900,
    ) -> None:
        """Arranca la aplicación BACnet local.

        local_address: p. ej. "192.168.1.10/24:47808".
        bbmd: dirección de un BBMD si hay que registrarse como foreign device.
        """
        argv = [
            "--name",
            device_name,
            "--instance",
            str(device_instance),
            "--address",
            local_address,
        ]
        if bbmd:
            argv += ["--foreign", bbmd, "--ttl", str(bbmd_ttl)]
        args = SimpleArgumentParser().parse_args(argv)
        self._app = Application.from_args(args)

    def close(self) -> None:
        if self._app is not None:
            self._app.close()
            self._app = None

    @property
    def app(self) -> Application:
        if self._app is None:
            raise RuntimeError("Cliente BACnet no iniciado")
        return self._app

    # -------------------------------------------------------------- descubrir
    async def discover(
        self,
        low: int | None = None,
        high: int | None = None,
        target: str | None = None,
        timeout: float = 3.0,
    ) -> list[BACnetDevice]:
        """Who-Is (broadcast, o unicast si se indica `target`)."""
        address = Address(target) if target else None
        iams = await self.app.who_is(low, high, address, timeout=timeout)
        devices: dict[int, BACnetDevice] = {}
        for iam in iams:
            instance = iam.iAmDeviceIdentifier[1]
            devices[instance] = BACnetDevice(
                instance=instance,
                address=str(iam.pduSource),
                vendor_id=int(iam.vendorID) if iam.vendorID is not None else None,
            )
        return sorted(devices.values(), key=lambda d: d.instance)

    async def read_device_name(self, address: str, instance: int) -> str | None:
        try:
            return str(
                await self.app.read_property(
                    Address(address), f"device,{instance}", "object-name"
                )
            )
        except Exception as err:  # noqa: BLE001 - dispositivo concreto puede fallar
            _LOGGER.debug("No se pudo leer el nombre de %s: %s", address, err)
            return None

    # --------------------------------------------------------------- objetos
    async def list_objects(self, address: str, instance: int) -> list[BACnetObject]:
        """Lee object-list y los nombres de los objetos soportados."""
        addr = Address(address)
        dev = ObjectIdentifier(f"device,{instance}")
        try:
            object_list = await self.app.read_property(addr, dev, "object-list")
        except Exception:  # noqa: BLE001
            # Algunos equipos no soportan leer el array entero: lectura por índice
            count = await self.app.read_property(addr, dev, "object-list", array_index=0)
            object_list = [
                await self.app.read_property(addr, dev, "object-list", array_index=i)
                for i in range(1, int(count) + 1)
            ]

        wanted: list[BACnetObject] = []
        for oid in object_list:
            otype = str(oid[0])
            if otype in POINT_TYPES or otype in (SCHEDULE_TYPE, CALENDAR_TYPE):
                wanted.append(BACnetObject(object_type=otype, instance=int(oid[1])))

        # nombres (y unidades / textos de estado) por RPM en bloques
        for i in range(0, len(wanted), RPM_CHUNK):
            chunk = wanted[i : i + RPM_CHUNK]
            params: list[Any] = []
            for obj in chunk:
                props = ["object-name", "description"]
                if obj.object_type.startswith("analog"):
                    props.append("units")
                if obj.object_type.startswith("multi-state"):
                    props.append("state-text")
                params += [obj.identifier, props]
            try:
                rows = await self.app.read_property_multiple(addr, params)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("RPM de nombres falló (%s); sigo sin nombres", err)
                continue
            by_id = {o.identifier: o for o in chunk}
            for oid, prop, _idx, val in rows:
                obj = by_id.get(f"{oid[0]},{oid[1]}")
                if obj is None or _is_error(val) or val is None:
                    continue
                if str(prop) == "object-name":
                    obj.name = str(val)
                elif str(prop) == "description":
                    obj.description = str(val) or None
                elif str(prop) == "units":
                    obj.units = str(val)
                elif str(prop) == "state-text":
                    obj.state_text = [str(s) for s in val]
        return wanted

    # ---------------------------------------------------------------- lectura
    async def read_present_values(
        self, address: str, objects: list[str]
    ) -> dict[str, Any]:
        """Lee present-value de varios objetos ('analog-value,1')."""
        addr = Address(address)
        result: dict[str, Any] = {}
        for i in range(0, len(objects), RPM_CHUNK):
            chunk = objects[i : i + RPM_CHUNK]
            params: list[Any] = []
            for oid in chunk:
                params += [oid, ["present-value"]]
            rows = await self.app.read_property_multiple(addr, params)
            for oid, _prop, _idx, val in rows:
                key = f"{oid[0]},{oid[1]}"
                if _is_error(val):
                    _LOGGER.debug("Error leyendo %s: %s", key, val)
                    result[key] = None
                else:
                    result[key] = _normalize_value(val)
        return result

    # -------------------------------------------------------------- escritura
    async def write_present_value(
        self,
        address: str,
        object_id: str,
        value: Any,
        priority: int | None = 8,
    ) -> None:
        """Escribe present-value. `value=None` libera la prioridad (Null)."""
        otype = object_id.split(",")[0]
        if value is None:
            bac_value: Any = Null(())
        elif otype.startswith("analog"):
            bac_value = Real(float(value))
        elif otype.startswith("binary"):
            bac_value = _binary_value(bool(value))
        elif otype.startswith("multi-state"):
            bac_value = Unsigned(int(value))
        else:
            raise ValueError(f"Tipo no escribible: {otype}")
        await self.app.write_property(
            Address(address), object_id, "present-value", bac_value, priority=priority
        )

    # --------------------------------------------------------------- horarios
    async def read_schedule(self, address: str, object_id: str) -> ScheduleData:
        addr = Address(address)
        rows = await self.app.read_property_multiple(
            addr,
            [
                object_id,
                [
                    "present-value",
                    "schedule-default",
                    "weekly-schedule",
                    "exception-schedule",
                ],
            ],
        )
        data = ScheduleData()
        for _oid, prop, _idx, val in rows:
            if _is_error(val):
                continue
            name = str(prop)
            if name == "present-value":
                data.present_value = _normalize_value(val)
            elif name == "schedule-default":
                data.default = _normalize_value(val)
            elif name == "weekly-schedule":
                data.weekly = [
                    [
                        {"time": _to_python(tv.time), "value": _normalize_value(tv.value)}
                        for tv in day.daySchedule
                    ]
                    for day in val
                ]
            elif name == "exception-schedule":
                data.exception_count = len(val)
        return data

    async def write_weekly_schedule(
        self,
        address: str,
        object_id: str,
        weekly: list[list[dict[str, Any]]],
    ) -> None:
        """Escribe weekly-schedule (7 días) respetando el tipo de datos del horario."""
        if len(weekly) != 7:
            raise ValueError("weekly debe tener 7 días (lunes..domingo)")
        addr = Address(address)
        default = await self.app.read_property(addr, object_id, "schedule-default")
        value_cls = default.get_value_type() if isinstance(default, AnyAtomic) else type(default)

        days = []
        for day in weekly:
            entries = []
            for entry in sorted(day, key=lambda e: e["time"]):
                hh, mm, *rest = (int(x) for x in str(entry["time"]).split(":"))
                ss = rest[0] if rest else 0
                entries.append(
                    TimeValue(
                        time=Time((hh, mm, ss, 0)),
                        value=_build_value(value_cls, entry["value"]),
                    )
                )
            days.append(DailySchedule(daySchedule=entries))
        await self.app.write_property(addr, object_id, "weekly-schedule", days)

    # -------------------------------------------------------------------- COV
    async def subscribe_cov(
        self,
        address: str,
        object_id: str,
        callback,
        lifetime: int = 300,
        confirmed: bool = False,
    ) -> None:
        """Suscribe a COV y llama a `callback(object_id, value)` con cada cambio.

        Se renueva solo mientras la tarea siga viva; si la suscripción cae el
        llamador debe volver a suscribir (el coordinador hace polling de respaldo).
        """
        addr = Address(address)
        oid = ObjectIdentifier(object_id)
        async with self.app.change_of_value(
            addr, oid, issue_confirmed_notifications=confirmed, lifetime=lifetime
        ) as scm:
            while not scm.is_fini:
                prop, value = await scm.get_value()
                if str(prop) == "present-value":
                    callback(object_id, _normalize_value(value))


def _binary_value(active: bool) -> Any:
    from bacpypes3.basetypes import BinaryPV

    return BinaryPV("active" if active else "inactive")


def _build_value(value_cls: type, raw: Any) -> Any:
    """Crea el valor atómico correcto para un horario según su tipo."""
    if value_cls is Boolean or value_cls.__name__ == "Boolean":
        return Boolean(bool(raw))
    if value_cls is Real or value_cls.__name__ in ("Real", "Double"):
        return Real(float(raw))
    if value_cls is Unsigned or value_cls.__name__ == "Unsigned":
        return Unsigned(int(raw))
    if value_cls is Integer or value_cls.__name__ == "Integer":
        return Integer(int(raw))
    if value_cls is CharacterString or value_cls.__name__ == "CharacterString":
        return CharacterString(str(raw))
    # Enumerated u otros: como Unsigned
    return Unsigned(int(raw))
