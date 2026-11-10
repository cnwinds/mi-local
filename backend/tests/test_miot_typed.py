import asyncio

from homehub.catalog import convert
from homehub.drivers.cloud import MiotGenericDriver
from homehub.drivers.miot_typed import TypedMapping
from homehub.miot_spec import parse

from test_cloud import FakeCloud


def prop(iid, name, fmt, access=("read", "write"), **extra):
    return {"iid": iid, "type": f"urn:miot-spec-v2:property:{name}:0000:x:1", "format": fmt, "access": list(access),
            **extra}


def service(iid, name, *props):
    return {"iid": iid, "type": f"urn:miot-spec-v2:service:{name}:0000:x:1", "properties": list(props)}


LIGHT = {"services": [service(2, "light", prop(1, "on", "bool"), prop(2, "brightness", "uint8", **{"value-range": [1, 100, 1]}),
                                prop(3, "color-temperature", "uint32", **{"value-range": [2700, 6500, 1]}))]}
AC = {"services": [
    service(2, "air-conditioner", prop(1, "on", "bool"),
            prop(2, "mode", "uint8", **{"value-list": [{"value": 1, "description": "Cool"}, {"value": 2, "description": "Dry"},
                                                       {"value": 4, "description": "Heat"}, {"value": 0, "description": "Auto"}]}),
            prop(4, "target-temperature", "float", **{"value-range": [16, 30, 0.5]})),
    service(3, "fan-control", prop(1, "fan-level", "uint8", **{"value-list": [
        {"value": 0, "description": "Auto"}, {"value": 1, "description": "Low"}, {"value": 2, "description": "Medium"},
        {"value": 3, "description": "High"}]}), prop(2, "vertical-swing", "bool")),
    service(4, "environment", prop(7, "temperature", "float", access=("read",))),
]}
CURTAIN = {"services": [service(2, "curtain", prop(2, "motor-control", "uint8", **{"value-list": [
    {"value": 0, "description": "Pause"}, {"value": 1, "description": "Open"}, {"value": 2, "description": "Close"}]}),
    prop(3, "current-position", "uint8", access=("read",)), prop(6, "target-position", "uint8", **{"value-range": [0, 100, 1]}))]}
OUTLET = {"services": [service(2, "switch", prop(1, "on", "bool")),
                       service(3, "power-consumption", prop(2, "electric-power", "float", access=("read",)))]}


def test_light_scales_brightness_and_kelvin():
    m = TypedMapping("light", parse(LIGHT, {}))
    assert m.state({"2.1": True, "2.2": 50, "2.3": 4600}) == {"power": True, "brightness": 50, "color_temp": 50}
    writes = m.writes("set_color_temp", 100, {})
    assert writes == {"2.1": True, "2.3": 6500}
    assert m.writes("toggle", None, {"2.1": True}) == {"2.1": False}


def test_ac_maps_modes_fan_and_caps_from_the_spec():
    m = TypedMapping("ac", parse(AC, {}))
    s = m.state({"2.1": True, "2.2": 4, "2.4": 24.5, "3.1": 2, "3.2": False, "4.7": 27.04})
    assert s["mode"] == "heat" and s["target_temp"] == 24.5 and s["fan_level"] == 2 and s["temperature"] == 27.0
    assert s["caps"] == {"modes": ["cool", "dry", "heat", "auto"], "temp_min": 16, "temp_max": 30, "temp_step": 0.5,
                         "fan_levels": 3}
    assert m.writes("set_mode", "dry", {}) == {"2.2": 2}
    assert m.writes("set_fan", 0, {}) == {"3.1": 0}
    assert m.writes("set_fan", 3, {}) == {"3.1": 3}


def test_curtain_uses_motor_control_and_target_position():
    m = TypedMapping("curtain", parse(CURTAIN, {}))
    assert m.state({"2.3": 40}) == {"position": 40}
    assert m.writes("open", None, {}) == {"2.2": 1}
    assert m.writes("stop", None, {}) == {"2.2": 0}
    assert m.writes("set_position", 130, {}) == {"2.6": 100}


def test_generic_driver_speaks_the_typed_commands():
    cloud = FakeCloud({(2, 1): True, (3, 2): 12.5})
    driver = MiotGenericDriver({"id": "9", "model": "x.plug.y", "kind": "plug"}, cloud, parse(OUTLET, {}))
    state = asyncio.run(driver.poll())
    assert state["power"] is True and state["load_power"] == 12.5
    asyncio.run(driver.command("toggle"))
    sets = [c[1]["params"] for c in cloud.calls if c[0] == "/miotspec/prop/set"]
    assert sets == [[{"did": "9", "siid": 2, "piid": 1, "value": False}]]


def test_import_types_by_spec_and_keeps_known_models():
    online = {"isOnline": True, "token": "t" * 32}
    light = convert({"did": 1, "model": "yeelink.light.ceiling10", "localip": "192.168.1.5", **online}, set(), "R", "light")
    assert light["driver"] == "yeelight"
    bulb = convert({"did": 2, "model": "opple.light.bydceiling", "localip": "10.0.0.8", **online}, set(), "R", "light")
    assert (bulb["kind"], bulb["driver"], bulb["ip"]) == ("light", "miio", "10.0.0.8")
    ac = convert({"did": 3, "model": "xiaomi.aircondition.ma2", "localip": "192.168.1.9", **online}, set(), "R",
                 "air-conditioner")
    assert ac["driver"] == "cloud"
    mesh = convert({"did": "blt.4", "model": "yeelink.light.mbulb3", "localip": "", "isOnline": True}, set(), "R", "light")
    assert (mesh["kind"], mesh["driver"], mesh["hidden"]) == ("light", "miot_cloud", False)
    assert convert({"did": 5, "model": "x.sensor.unknown", "localip": ""}, set(), "R", None) is None
    assert convert({"did": 6, "model": "chuangmi.camera.ipc009", "localip": "192.168.1.7", **online}, set(), "R",
                   "camera") is None
    wan = convert({"did": 7, "model": "x.fan.y", "localip": "8.8.8.8", **online}, set(), "R", "fan")
    assert (wan["driver"], wan["kind"], wan["hidden"]) == ("miot_cloud", "other", True)
    assert convert({"did": 8, "model": "miir.aircondition.ir02", "localip": ""}, set(), "R", "air-conditioner") is None
    assert convert({"did": 9, "model": "xiaomi.router.rm1800", "localip": ""}, set(), "R", "router") is None
