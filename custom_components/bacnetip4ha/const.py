"""Constantes de BACnetIP4HA."""

DOMAIN = "bacnetip4ha"

CONF_LOCAL_ADDRESS = "local_address"
CONF_BBMD = "bbmd"
CONF_DEVICE_ADDRESS = "device_address"
CONF_DEVICE_INSTANCE = "device_instance"
CONF_OBJECTS = "objects"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_WRITE_PRIORITY = "write_priority"

DEFAULT_PORT = 47808
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_WRITE_PRIORITY = 8

SERVICE_GET_SCHEDULE = "get_schedule"
SERVICE_SET_WEEKLY_SCHEDULE = "set_weekly_schedule"

# unidades BACnet -> unidad de Home Assistant (las no listadas se muestran tal cual)
UNITS_MAP = {
    "degrees-celsius": "°C",
    "degrees-fahrenheit": "°F",
    "kelvin": "K",
    "percent": "%",
    "percent-relative-humidity": "%",
    "pascals": "Pa",
    "kilopascals": "kPa",
    "bars": "bar",
    "watts": "W",
    "kilowatts": "kW",
    "kilowatt-hours": "kWh",
    "volts": "V",
    "amperes": "A",
    "hertz": "Hz",
    "parts-per-million": "ppm",
    "liters-per-second": "L/s",
    "cubic-meters-per-hour": "m³/h",
    "cubic-meters": "m³",
    "seconds": "s",
    "minutes": "min",
    "hours": "h",
}
