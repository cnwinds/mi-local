import asyncio

import pytest

from homehub.drivers.cloud import MiotGenericDriver
from homehub.drivers.miot_transport import HybridTransport
from homehub.miot_spec import parse

from test_miot_typed import LIGHT


class Fake:
    def __init__(self, name, values=None, fail=False, code=0):
        self.name, self.values, self.fail, self.code, self.calls = name, values or {}, fail, code, []

    async def get(self, params):
        self.calls.append(("get", params))
        if self.fail:
            raise OSError("no response")
        return [{**p, "code": self.code, "value": self.values.get((p["siid"], p["piid"]))} for p in params]

    async def set(self, params):
        self.calls.append(("set", params))
        if self.fail:
            raise OSError("no response")
        return [{**p, "code": self.code} for p in params]

    async def rpc(self, method, params):
        self.calls.append(("rpc", method))
        return []


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


PARAMS = [{"did": "1", "siid": 2, "piid": 1}]


def test_lan_first_then_cloud_while_lan_is_down_then_lan_again():
    lan, cloud, clock = Fake("lan", {(2, 1): True}, fail=True), Fake("cloud", {(2, 1): True}), Clock()
    t = HybridTransport(lan, cloud, clock)
    assert t.name == "lan"
    assert asyncio.run(t.get(PARAMS))[0]["value"] is True
    assert t.name == "cloud" and len(cloud.calls) == 1
    asyncio.run(t.get(PARAMS))
    assert len(lan.calls) == 1 and len(cloud.calls) == 2
    lan.fail = False
    clock.t += HybridTransport.LAN_RETRY + 1
    asyncio.run(t.get(PARAMS))
    assert t.name == "lan" and len(lan.calls) == 2 and len(cloud.calls) == 2


def test_lan_that_answers_no_property_counts_as_unsupported():
    lan, cloud = Fake("lan", code=-4004), Fake("cloud", {(2, 1): False})
    t = HybridTransport(lan, cloud, Clock())
    assert asyncio.run(t.get(PARAMS))[0]["code"] == 0
    assert t.name == "cloud"


def test_without_cloud_lan_errors_surface():
    t = HybridTransport(Fake("lan", fail=True), None, Clock())
    with pytest.raises(OSError):
        asyncio.run(t.get(PARAMS))
    assert t.name == "lan"


def test_light_on_the_lan_polls_fast_and_writes_locally():
    lan, cloud = Fake("lan", {(2, 1): True, (2, 2): 80, (2, 3): 2700}), Fake("cloud")
    t = HybridTransport(lan, cloud, Clock())
    driver = MiotGenericDriver({"id": "1", "model": "x.light.y", "kind": "light"}, None, parse(LIGHT, {}), t)
    state = asyncio.run(driver.poll())
    assert (state["power"], state["brightness"], state["color_temp"]) == (True, 80, 0)
    assert driver.poll_interval == 5.0
    asyncio.run(driver.command("set_brightness", 30))
    assert lan.calls[-1][0] == "set" and not cloud.calls
