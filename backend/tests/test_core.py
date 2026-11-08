import asyncio

from homehub.drivers.gateway2 import Gateway2, norm_sid, parse_state
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


def test_gateway_id_list_ack_resolves_pending_request():
    async def scenario():
        gw = Gateway2("192.168.1.120", "04cf8c000001", "k" * 16, "0.0.0.0", lambda *a: None, lambda *a: None)
        fut = asyncio.get_running_loop().create_future()
        gw._pending[("get_id_list_ack", norm_sid(gw.sid))] = fut
        gw._handle({"cmd": "get_id_list_ack", "sid": "04cf8c000001", "data": '["158d0000000001"]'}, ("192.168.1.120", 9898))
        return await fut

    assert asyncio.run(scenario()) == ["158d0000000001"]


def test_gateway_error_reply_does_not_mark_online():
    seen = []
    gw = Gateway2("192.168.1.120", "04cf8c000001", "k" * 16, "0.0.0.0", lambda *a: seen.append(a), lambda *a: None)
    gw._handle({"cmd": "read_ack", "sid": "158d0000000002", "data": '{"error":"No device"}'}, ("192.168.1.120", 9898))
    assert seen == []
    gw._handle({"cmd": "read_ack", "model": "switch", "sid": "158d0000000001", "data": '{"voltage":3000}'}, ("192.168.1.120", 9898))
    assert seen == [("158d0000000001", "switch", {"online": True, "battery": 50})]


def test_doorbell_rings_on_the_gateway_itself():
    from homehub.drivers.gateway2 import Gw2DoorbellDriver

    class FakeGateway:
        sid = "4cf8c000001"
        writes = []

        async def write(self, sid, params):
            self.writes.append((sid, params))

    gw = FakeGateway()
    driver = Gw2DoorbellDriver({"tone": 11, "volume": 40}, gw)
    asyncio.run(driver.command("ring"))
    asyncio.run(driver.command("stop"))
    assert gw.writes == [("4cf8c000001", {"mid": 11, "vol": 40}), ("4cf8c000001", {"mid": 10000})]


def test_gateway_table_parses_device_list():
    from homehub.hub import Hub

    class FakeDevice:
        def send(self, cmd, params):
            return ["lumi.158d0000000003", 13, 1, 0, 1, "lumi.158d0003133f31", 56, 0, 0, 8, "lumi.0", 0, 0, 0, 0]

    table = asyncio.run(Hub._gw_table(FakeDevice()))
    assert table == {"158d0000000003": True, "158d0003133f31": False}
