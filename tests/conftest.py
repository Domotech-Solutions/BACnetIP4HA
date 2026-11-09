"""Fixtures: un dispositivo BACnet simulado en loopback (sin HA)."""

import sys
from pathlib import Path

import pytest_asyncio

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "custom_components" / "bacnetip4ha")
)

from bacpypes3.app import Application  # noqa: E402
from bacpypes3.argparse import SimpleArgumentParser  # noqa: E402
from bacpypes3.basetypes import DailySchedule, DateRange, TimeValue  # noqa: E402
from bacpypes3.local.analog import AnalogValueObject  # noqa: E402
from bacpypes3.local.binary import BinaryValueObject  # noqa: E402
from bacpypes3.local.object import Object as LocalObject  # noqa: E402
from bacpypes3.object import ScheduleObject as _Schedule  # noqa: E402
from bacpypes3.primitivedata import Date, Real, Time  # noqa: E402

SERVER = "127.0.0.1:47830"
CLIENT = "127.0.0.1:47831"
DEVICE_INSTANCE = 1001


class SimSchedule(LocalObject, _Schedule):
    """Schedule que solo almacena propiedades (sin interpretar)."""


def _day(hhmm: str, value: float) -> DailySchedule:
    return DailySchedule(daySchedule=[TimeValue(time=Time(hhmm + ":00.00"), value=Real(value))])


@pytest_asyncio.fixture
async def sim_device():
    argv = ["--name", "sim", "--instance", str(DEVICE_INSTANCE), "--address", SERVER]
    app = Application.from_args(SimpleArgumentParser().parse_args(argv))
    app.add_object(
        AnalogValueObject(
            objectIdentifier=("analogValue", 1),
            objectName="consigna",
            presentValue=21.5,
            statusFlags=[0, 0, 0, 0],
            units="degreesCelsius",
            description="Consigna sala",
        )
    )
    app.add_object(
        BinaryValueObject(
            objectIdentifier=("binaryValue", 1),
            objectName="marcha",
            presentValue="inactive",
            statusFlags=[0, 0, 0, 0],
        )
    )
    app.add_object(
        SimSchedule(
            objectIdentifier=("schedule", 1),
            objectName="horario",
            presentValue=Real(0.0),
            scheduleDefault=Real(10.0),
            effectivePeriod=DateRange(startDate=Date("*-*-*"), endDate=Date("*-*-*")),
            weeklySchedule=[_day("08:00", 21.0) for _ in range(7)],
            statusFlags=[0, 0, 0, 0],
        )
    )
    yield app
    app.close()
