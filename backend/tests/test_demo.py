import asyncio

from homehub.demo import DEVICES, ROOMS, DemoDriver


def run(driver, *command):
    asyncio.run(driver.command(*command))
    return asyncio.run(driver.poll())


def test_demo_devices_answer_like_real_ones():
    light = DemoDriver({"kind": "light", "demo": {"power": False, "brightness": 50}})
    assert run(light, "toggle")["power"] is True
    assert run(light, "set_brightness", 130)["brightness"] == 100
    ac = DemoDriver({"kind": "ac", "demo": {"power": True, "mode": "cool", "target_temp": 26}})
    assert run(ac, "set_mode", "heat")["mode"] == "heat"
    curtain = DemoDriver({"kind": "curtain", "demo": {"position": 30}})
    assert run(curtain, "open")["position"] == 100
    heater = DemoDriver({"kind": "bath_heater", "demo": {"power": False, "light": False, "heating": False}})
    assert run(heater, "set_heating", True)["power"] is True


def test_demo_home_is_consistent():
    assert {room for _, _, room, *_ in DEVICES} <= set(ROOMS)
    assert len({d[0] for d in DEVICES}) == len(DEVICES)
