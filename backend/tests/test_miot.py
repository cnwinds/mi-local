import asyncio

import pytest

from homehub.drivers.cloud import MiotGenericDriver
from homehub.miot_spec import parse

from test_cloud import FakeCloud

HOOD = {"services": [
    {"iid": 1, "type": "urn:miot-spec-v2:service:device-information:00007801:viomi-c1:1", "description": "Device Information",
     "properties": [{"iid": 1, "type": "urn:miot-spec-v2:property:manufacturer:00000001:viomi-c1:1", "format": "string",
                     "access": ["read"]}]},
    {"iid": 2, "type": "urn:miot-spec-v2:service:hood:00007828:viomi-c1:1", "description": "Hood",
     "properties": [{"iid": 1, "type": "urn:miot-spec-v2:property:on:00000006:viomi-c1:1", "description": "Switch Status",
                     "format": "bool", "access": ["read", "write", "notify"]}]},
    {"iid": 3, "type": "urn:miot-spec-v2:service:fan-control:00007808:viomi-c1:1", "description": "Fan Control",
     "properties": [{"iid": 1, "type": "urn:miot-spec-v2:property:fan-level:00000016:viomi-c1:1", "format": "uint8",
                     "access": ["read", "write"], "value-list": [{"value": 1, "description": "Low"},
                                                                 {"value": 3, "description": "Stir-fry"}]}]},
    {"iid": 4, "type": "urn:miot-spec-v2:service:water-heater:0000782A:viomi-u1:1", "description": "Water Heater",
     "properties": [
         {"iid": 2, "type": "urn:miot-spec-v2:property:target-temperature:00000021:viomi-u1:1", "format": "uint8",
          "unit": "celsius", "access": ["read", "write"], "value-range": [30, 65, 1]},
         {"iid": 9, "type": "urn:hfjh-spec:property:light-mode-list:00000001:hfjh-m100:1", "format": "string",
          "access": ["read", "write"]},
     ]},
]}


def test_parse_uses_translation_then_fallbacks_and_drops_noise():
    fields = parse(HOOD, {"service:003:property:001": "抽风档位", "service:003:property:001:valuelist:001": "爆炒档"})
    by_key = {f["key"]: f for f in fields}
    assert set(by_key) == {"2.1", "3.1", "4.2"}
    assert by_key["2.1"]["service"] == "油烟机" and by_key["2.1"]["name"] == "开关"
    assert by_key["3.1"]["name"] == "抽风档位"
    assert [v["label"] for v in by_key["3.1"]["values"]] == ["低档", "爆炒档"]
    assert by_key["4.2"]["unit"] == "celsius" and by_key["4.2"]["writable"]


def test_generic_driver_reads_props_and_writes_within_spec():
    fields = parse(HOOD, {})
    cloud = FakeCloud({(2, 1): True, (4, 2): 47}, rpc=[1, 180])
    driver = MiotGenericDriver({"id": "1", "model": "viomi.hood.c1"}, cloud, fields)
    state = asyncio.run(driver.poll())
    assert state["power"] is True
    assert state["props"] == {"2.1": True, "4.2": 47, "x.link_state": 1, "x.poweroff_delaytime": 180}

    asyncio.run(driver.command("set_prop", {"key": "4.2", "value": 70.4}))
    asyncio.run(driver.command("turn_off"))
    sets = [c[1]["params"][0] for c in cloud.calls if c[0] == "/miotspec/prop/set"]
    assert [(s["siid"], s["piid"], s["value"]) for s in sets] == [(4, 2, 65), (2, 1, False)]
    with pytest.raises(ValueError):
        asyncio.run(driver.command("set_prop", {"key": "3.1", "value": 2}))
    with pytest.raises(ValueError):
        asyncio.run(driver.command("set_prop", {"key": "x.link_state", "value": 0}))
