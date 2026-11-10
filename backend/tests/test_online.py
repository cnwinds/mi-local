import asyncio

import pytest

from homehub.hub import FAILURE_RETRY, OFFLINE_AFTER_FAILURES, Hub


class FlakyDriver:
    poll_interval = 300.0
    offline_retry = 300.0

    def __init__(self, results):
        self.results = list(results)

    async def poll(self):
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def make_hub(driver) -> Hub:
    hub = Hub.__new__(Hub)
    hub.records, hub.subscribers, hub._poll_failures = {}, set(), {}
    hub.states = {"d": {"online": True, "power": True}}
    hub.drivers = {"d": driver}
    return hub


def test_single_lost_reply_keeps_device_online():
    hub = make_hub(FlakyDriver([TimeoutError(), TimeoutError(), {"power": False}]))
    for _ in range(2):
        assert asyncio.run(hub.refresh("d")) == {"online": True, "power": True}
    assert asyncio.run(hub.refresh("d")) == {"online": True, "power": False}
    assert hub._poll_failures == {}


def test_run_of_failures_marks_offline():
    hub = make_hub(FlakyDriver([TimeoutError()] * OFFLINE_AFTER_FAILURES))
    for _ in range(OFFLINE_AFTER_FAILURES - 1):
        asyncio.run(hub.refresh("d"))
    assert hub.states["d"]["online"]
    assert asyncio.run(hub.refresh("d"))["online"] is False


def test_failed_poll_is_retried_soon(monkeypatch):
    driver = FlakyDriver([TimeoutError(), {"power": True}])
    hub = make_hub(driver)
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(hub._poll_loop("d"))
    assert sleeps == [FAILURE_RETRY, driver.poll_interval]
