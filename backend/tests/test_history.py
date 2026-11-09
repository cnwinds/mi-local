import time

from homehub.history import History


def make(tmp_path):
    return History(tmp_path / "events.db")


def test_keeps_everything_and_pages(tmp_path):
    h = make(tmp_path)
    for i in range(2500):
        h.add_event(1000 + i, "lumi.sw", "click")
    page = h.events(limit=100)
    assert page["total"] == 2500
    assert page["items"][0]["ts"] == 3499
    older = h.events(before=page["items"][-1]["ts"], limit=100)
    assert older["items"][0]["ts"] == page["items"][-1]["ts"] - 1


def test_import_runs_once(tmp_path):
    h = make(tmp_path)
    old = [{"ts": 1.0, "device": "a", "event": "click"}]
    h.import_events(old)
    h.import_events(old)
    assert h.events()["total"] == 1


def test_stats_usage_and_presses(tmp_path):
    h = make(tmp_path)
    now = time.time()
    h.add_power(now - 7200, "light.a", True)
    h.add_power(now - 3600, "light.a", False)
    h.add_power(now - 1800, "light.a", True)  # still on: 30 more minutes
    for _ in range(3):
        h.add_event(now - 600, "lumi.sw", "click")
    h.add_event(now - 500, "lumi.sw", "double_click")
    h.add_event(now - 400, "lockin.x", "door_open")
    s = h.stats(7, 0, {"lumi.sw": "switch", "lockin.x": "lock", "light.a": "light"})
    assert s["total_presses"] == 4
    assert s["press_types"] == {"click": 3, "double_click": 1}
    assert s["total_doors"] == 1
    assert s["switches"] == [{"device": "lumi.sw", "count": 4}]
    usage = s["usage"][0]
    assert usage["device"] == "light.a" and usage["turn_ons"] == 2
    assert abs(usage["on_seconds"] - 5400) < 5
    assert sum(map(sum, s["heatmap"])) == 4 + 2 + 1


def test_stats_counts_device_on_before_range(tmp_path):
    h = make(tmp_path)
    now = time.time()
    h.add_power(now - 10 * 86400, "plug.a", True)
    s = h.stats(1, 0, {})
    assert abs(s["usage"][0]["on_seconds"] - 86400) < 5
    assert s["usage"][0]["turn_ons"] == 0
