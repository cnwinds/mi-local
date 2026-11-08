from homehub.catalog import merge, rooms_from_homes

GW = {"did": "100000001", "model": "lumi.gateway.v3", "name": "网关2", "mac": "04:CF:8C:00:00:01", "localip": "192.168.1.120"}
LIGHT = {"did": "100000002", "model": "yeelink.light.ceiling10", "name": "餐厅灯", "localip": "192.168.1.122",
         "token": "t1", "isOnline": True}
SWITCH = {"did": "lumi.158d0000000001", "model": "lumi.sensor_switch.v2", "name": "餐厅开关", "parent_id": "100000001"}


def test_rooms_from_homes():
    homes = [{"rooms": [{"name": "餐厅", "dids": ["100000002"]}, {"name": "卧室", "dids": []}]}]
    assert rooms_from_homes(homes) == ({"100000002": "餐厅"}, ["餐厅", "卧室"])


def test_cloud_wins_for_name_room_token_but_hidden_is_local():
    existing = {"100000002": {"id": "100000002", "name": "旧名字", "room": "未分配", "token": "old", "hidden": True,
                              "ip": "192.168.1.122", "kind": "light", "driver": "yeelight"}}
    records, summary = merge([GW, LIGHT], {"100000002": "餐厅"}, existing, "100000001", "KEY")
    light = next(r for r in records if r["id"] == "100000002")
    assert (light["name"], light["room"], light["token"], light["hidden"]) == ("餐厅灯", "餐厅", "t1", True)
    assert summary["renamed"] == ["旧名字 → 餐厅灯"]
    assert summary["token_changed"] == ["餐厅灯"]


def test_gateway_keeps_lan_key_and_switch_maps_to_gateway2():
    records, summary = merge([GW, SWITCH], {}, {}, "100000001", "KEY")
    by_id = {r["id"]: r for r in records}
    assert by_id["100000001"]["lan_key"] == "KEY"
    assert by_id["100000001"]["sid"] == "04cf8c000001"
    assert by_id["lumi.158d0000000001"]["driver"] == "gw2"
    assert by_id["lumi.158d0000000001"]["sid"] == "158d0000000001"
    assert set(summary["added"]) == {"网关2", "餐厅开关"}


def test_local_name_and_room_survive_sync():
    existing = {"lumi.158d0000000001": {"id": "lumi.158d0000000001", "name": "小米无线开关", "room": "客厅走道",
                                        "local_name": "餐厅灯开关", "local_room": "餐厅", "name_auto": True,
                                        "kind": "switch", "driver": "gw2", "sid": "158d0000000001"}}
    records, _ = merge([GW, SWITCH], {}, existing, "100000001", "KEY")
    sw = next(r for r in records if r["id"] == "lumi.158d0000000001")
    assert (sw["name"], sw["local_name"], sw["local_room"], sw["name_auto"]) == ("餐厅开关", "餐厅灯开关", "餐厅", True)


def test_local_only_devices_are_kept():
    local = {"lumi.abc": {"id": "lumi.abc", "name": "本地发现", "kind": "switch"}}
    records, _ = merge([GW], {}, local, "100000001", "KEY")
    assert any(r["id"] == "lumi.abc" for r in records)
