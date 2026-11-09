# BACnetIP4HA

Integración BACnet/IP para Home Assistant (HACS), basada en [bacpypes3](https://github.com/JoelBender/bacpypes3).

> Estado: **0.1.0, en desarrollo**. Probada contra un dispositivo BACnet simulado; falta validarla con controladores reales.

## Qué hace

- Descubrimiento de dispositivos (Who-Is / I-Am) o alta manual por IP y device instance.
- Registro como *foreign device* en un BBMD para redes en distintas subredes.
- Lectura de puntos con ReadPropertyMultiple y escritura con prioridad configurable (1-16).
- **Objetos Schedule**: lectura del horario semanal y escritura mediante servicios.

| Objeto BACnet | Entidad HA |
|---|---|
| analog-input, multi-state-input | `sensor` |
| analog-value, analog-output, multi-state-value, multi-state-output | `number` (escribible) |
| binary-input | `binary_sensor` |
| binary-value, binary-output | `switch` |
| schedule | `sensor` (estado = present-value, atributos = horario semanal) |

## Servicios de horarios

Sobre la entidad `sensor` de un Schedule:

- `bacnetip4ha.get_schedule` — devuelve `present_value`, `default`, `weekly` y `exception_entries`.
- `bacnetip4ha.set_weekly_schedule` — escribe `weekly`: 7 listas (lunes a domingo) de `{time, value}`.

```yaml
action: bacnetip4ha.set_weekly_schedule
target:
  entity_id: sensor.mi_horario
data:
  weekly:
    - [{time: "07:30", value: 22}, {time: "20:00", value: 17}]   # lunes
    - [{time: "07:30", value: 22}, {time: "20:00", value: 17}]
    - [{time: "07:30", value: 22}, {time: "20:00", value: 17}]
    - [{time: "07:30", value: 22}, {time: "20:00", value: 17}]
    - [{time: "07:30", value: 22}, {time: "20:00", value: 17}]
    - []                                                       # sábado
    - []                                                       # domingo
```

El tipo del valor (real, booleano, entero...) se toma del `schedule-default` del propio objeto.

## Instalación

1. HACS → menú ⋮ → *Repositorios personalizados* → URL de este repositorio, categoría *Integración*.
2. Instalar y reiniciar Home Assistant.
3. *Ajustes → Dispositivos y servicios → Añadir integración → BACnet/IP*.

## Limitaciones conocidas (0.1.0)

- Un único socket UDP por instancia de HA: no puede coexistir en el mismo puerto (47808) con otra integración BACnet, p. ej. el add-on de Bepacom. Usa otro puerto en uno de los dos.
- Home Assistant OS necesita red con acceso al segmento BACnet (el broadcast no cruza routers: usa BBMD o alta manual).
- Las suscripciones COV están implementadas en el cliente pero **todavía no se usan ni se han probado**; el estado se obtiene por sondeo.
- `exception-schedule` y `calendar` solo se cuentan/listan, aún no se editan.
- Un objeto Schedule cuyos valores no sean real/booleano/entero/unsigned/cadena se escribe como unsigned.

## Desarrollo

```bash
python -m venv .venv && . .venv/bin/activate
pip install bacpypes3==0.0.110 pytest pytest-asyncio
pytest
```

Los tests levantan un dispositivo BACnet simulado en `127.0.0.1` y no requieren Home Assistant.
