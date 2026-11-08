from homehub.drivers.gateway2 import norm_sid, parse_state
from homehub.rules import matches, resolve_toggles

RULE = {"enabled": True, "trigger": {"type": "device_event", "device": "lumi.a", "event": "click"}, "actions": []}


def test_matches_event():
    assert matches(RULE, "lumi.a", "click")
    assert not matches(RULE, "lumi.a", "double_click")
    assert not matches({**RULE, "enabled": False}, "lumi.a", "click")


def test_group_toggle_turns_all_off_when_any_on():
    actions = [{"device": "a", "action": "toggle"}, {"device": "b", "action": "toggle"}]
    assert {a["action"] for a in resolve_toggles(actions, {"a": False, "b": True})} == {"turn_off"}
    assert {a["action"] for a in resolve_toggles(actions, {"a": False, "b": False})} == {"turn_on"}


def test_non_toggle_actions_untouched():
    actions = [{"device": "a", "action": "toggle"}, {"device": "c", "action": "close"}]
    assert resolve_toggles(actions, {"a": True})[1]["action"] == "close"


def test_parse_gateway_states():
    assert parse_state("plug", {"voltage": 3600, "status": "on", "load_power": "12.5"}) == {"power": True, "load_power": 12.5}
    assert parse_state("curtain", {"voltage": 3600, "curtain_level": "40"}) == {"position": 40}
    assert parse_state("switch", {"voltage": 3000}) == {"battery": 50}


def test_norm_sid():
    assert norm_sid("04cf8c000001") == norm_sid("4cf8c000001")
