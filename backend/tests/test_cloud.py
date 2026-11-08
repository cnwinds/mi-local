import asyncio

from homehub.catalog import convert
from homehub.drivers.cloud import AcPartnerV2, AirerDriver, BathHeaterDriver, XiaomiAcC1


class FakeCloud:
    def __init__(self, values: dict | None = None, rpc=None):
        self.values = values or {}
        self.rpc = rpc
        self.calls = []

    def call(self, path, payload):
        self.calls.append((path, payload))
        if path == "/miotspec/prop/get":
            return [{**p, "code": 0, "value": self.values[(p["siid"], p["piid"])]}
                    if (p["siid"], p["piid"]) in self.values else {**p, "code": -1} for p in payload["params"]]
        if path == "/miotspec/prop/set":
            return [{**p, "code": 0} for p in payload["params"]]
        return self.rpc


def test_ac_c1_state_and_commands():
    cloud = FakeCloud({(2, 1): False, (2, 2): 2, (2, 3): 25, (3, 1): 2, (3, 2): False, (4, 1): 22})
    ac = XiaomiAcC1({"id": "116359039"}, cloud)
    state = asyncio.run(ac.poll())
    assert state["mode"] == "cool" and state["target_temp"] == 25 and state["temperature"] == 22
    assert state["caps"]["temp_step"] == 0.5 and "auto" not in state["caps"]["modes"]

    asyncio.run(ac.command("set_temp", 26.3))
    asyncio.run(ac.command("set_mode", "heat"))
    asyncio.run(ac.command("toggle"))
    sets = [c[1]["params"][0] for c in cloud.calls if c[0] == "/miotspec/prop/set"]
    assert [(s["siid"], s["piid"], s["value"]) for s in sets] == [(2, 3, 26.5), (2, 2, 5), (2, 1, True)]


def test_acpartner_clamps_whole_degrees():
    cloud = FakeCloud()
    asyncio.run(AcPartnerV2({"id": "1"}, cloud).command("set_temp", 35))
    assert cloud.calls[0][1]["params"][0]["value"] == 30


def test_bath_heater_off_stops_everything():
    cloud = FakeCloud({(2, 1): True, (3, 2): "30", (3, 3): "21", (3, 4): False, (3, 5): False, (3, 6): True})
    heater = BathHeaterDriver({"id": "1"}, cloud)
    state = asyncio.run(heater.poll())
    assert state["power"] and state["temperature"] == 21.0
    asyncio.run(heater.command("toggle"))
    values = {(p["siid"], p["piid"]): p["value"] for p in cloud.calls[-1][1]["params"]}
    assert values == {(2, 1): False, (3, 4): False, (3, 5): False, (3, 6): False}


def test_airer_uses_legacy_rpc():
    cloud = FakeCloud(rpc=["0", "1", "2", "000", "1"])
    airer = AirerDriver({"id": "106345963"}, cloud)
    assert asyncio.run(airer.poll())["motor"] == "down"
    asyncio.run(airer.command("up"))
    assert cloud.calls[-1] == ("/home/rpc/106345963", {"method": "set_motor", "params": [1]})


def test_catalog_maps_cloud_models_without_lan_details():
    record = convert({"did": 116359039, "model": "xiaomi.aircondition.ma2", "name": "卧室空调"}, set(), "卧室")
    assert record["kind"] == "ac" and record["driver"] == "cloud" and "ip" not in record
