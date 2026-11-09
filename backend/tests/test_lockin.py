import asyncio

import pytest

from homehub.drivers.lockin import LockinLockDriver, build_sign, describe, java_urlencode


def test_java_urlencode():
    assert java_urlencode("a b*-_.~:中") == "a+b*-_.%7E%3A%E4%B8%AD"


def test_sign_is_stable_and_order_independent():
    a = build_sign("get", "/api/v1/device/", {"key": "k", "access_token": "t:1", "timestamp": "1"})
    b = build_sign("get", "/api/v1/device/", {"timestamp": "1", "access_token": "t:1", "key": "k"})
    assert a == b and len(a) == 32


def test_describe():
    assert describe({"source_name": "张三", "source": 3}) == "张三用指纹开锁"
    assert describe({"source": 8}) == "用人脸开锁"
    assert describe({}) == "门锁已打开"


class FakeCloud:
    def __init__(self):
        self.door, self.records = 2, []

    async def get(self, path, extra=None):
        if path == "/api/lock/v1/info":
            return {"device": {"locker_status": {"doorstate": self.door}, "power": 80, "onoff_line": 1}}
        return {"family_record": self.records}


def test_events_fire_only_for_changes_after_first_poll():
    cloud, events = FakeCloud(), []
    cloud.records = [{"uuid": "u", "eventid": 2203, "time": 1000, "detail": {"source": 3, "source_name": "张三"}}]
    driver = LockinLockDriver({"lockin_uuid": "u"}, cloud, events.append)
    state = asyncio.run(driver.poll())
    assert state == {"door": "closed", "battery": 80, "lock_online": True, "last_event": "张三用指纹开锁",
                     "last_event_ts": 1.0}
    assert events == []
    cloud.door = 1
    cloud.records.append({"uuid": "u", "eventid": 2203, "time": 2000, "detail": {"source": 8}})
    state = asyncio.run(driver.poll())
    assert events == ["unlock", "door_open"]
    assert state["last_event"] == "用人脸开锁"
    cloud.door = 2
    asyncio.run(driver.poll())
    assert events == ["unlock", "door_open", "door_close"]


def test_lock_is_read_only():
    driver = LockinLockDriver({"lockin_uuid": "u"}, FakeCloud(), lambda e: None)
    with pytest.raises(ValueError):
        asyncio.run(driver.command("unlock"))
