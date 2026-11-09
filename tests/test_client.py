import pytest

from client import BACnetClient
from conftest import CLIENT, DEVICE_INSTANCE, SERVER


@pytest.fixture
async def client(sim_device):
    c = BACnetClient()
    await c.start(CLIENT, device_instance=2002)
    yield c
    c.close()


async def test_discover_unicast(client):
    devices = await client.discover(DEVICE_INSTANCE, DEVICE_INSTANCE, target=SERVER)
    assert [d.instance for d in devices] == [DEVICE_INSTANCE]


async def test_list_objects(client):
    objs = await client.list_objects(SERVER, DEVICE_INSTANCE)
    ids = {o.identifier: o for o in objs}
    assert {"analog-value,1", "binary-value,1", "schedule,1"} <= set(ids)
    assert ids["analog-value,1"].name == "consigna"
    assert ids["analog-value,1"].units == "degrees-celsius"


async def test_read_and_write_point(client):
    vals = await client.read_present_values(SERVER, ["analog-value,1", "binary-value,1"])
    assert vals == {"analog-value,1": 21.5, "binary-value,1": False}
    await client.write_present_value(SERVER, "analog-value,1", 23.0, priority=8)
    await client.write_present_value(SERVER, "binary-value,1", True, priority=8)
    vals = await client.read_present_values(SERVER, ["analog-value,1", "binary-value,1"])
    assert vals == {"analog-value,1": 23.0, "binary-value,1": True}


async def test_schedule_read_write(client):
    sched = await client.read_schedule(SERVER, "schedule,1")
    assert sched.default == 10.0
    assert len(sched.weekly) == 7
    assert sched.weekly[0] == [{"time": "08:00:00", "value": 21.0}]

    new_week = [
        [{"time": "07:30:00", "value": 22.0}, {"time": "20:00:00", "value": 17.0}]
    ] * 5 + [[], []]
    await client.write_weekly_schedule(SERVER, "schedule,1", new_week)
    sched = await client.read_schedule(SERVER, "schedule,1")
    assert sched.weekly[0] == new_week[0]
    assert sched.weekly[6] == []
