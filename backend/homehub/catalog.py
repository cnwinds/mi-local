"""Map Mi Home cloud devices to local device records and merge them into the existing set."""

UNASSIGNED = "未分配"
LIGHT_DRIVERS = {"yeelink.light.ceiling": "yeelight", "philips.light.downlight": "philips"}
GW2_KINDS = {"lumi.sensor_switch.v2": "switch", "lumi.plug.v1": "plug", "lumi.curtain.v1": "curtain"}
SKIP_MODELS = ("camera",)
SYNCED_FIELDS = ("name", "room", "model", "ip", "token")


def convert(dev: dict, gateway_ids: set[str], room: str) -> dict | None:
    model = dev.get("model", "")
    base = {"id": str(dev["did"]), "name": dev.get("name", model), "room": room, "model": model, "hidden": False}
    # Zigbee devices still on the multimode gateway are mapped to Gateway 2 too: they show
    # offline until re-paired to Gateway 2, which keeps the same Zigbee address.
    if model in GW2_KINDS and str(dev.get("parent_id")) in gateway_ids:
        sid = str(dev["did"]).removeprefix("lumi.")
        kind = GW2_KINDS[model]
        return {**base, "id": f"lumi.{sid}", "kind": kind, "driver": "gw2", "sid": sid, "gw_model": kind}
    ip, token = dev.get("localip") or "", dev.get("token")
    if not token or not ip.startswith("192.168.") or any(s in model for s in SKIP_MODELS):
        return None
    if model.startswith("lumi.gateway"):
        return None
    for prefix, driver in LIGHT_DRIVERS.items():
        if model.startswith(prefix):
            return {**base, "kind": "light", "driver": driver, "ip": ip, "token": token}
    return {**base, "kind": "other", "driver": "miio", "ip": ip, "token": token, "hidden": not dev.get("isOnline")}


def gateway_record(dev: dict, room: str, lan_key: str, ip: str | None = None) -> dict:
    return {
        "id": str(dev["did"]), "name": dev.get("name", "网关"), "room": room, "kind": "gateway",
        "model": dev["model"], "hidden": True, "ip": ip or dev.get("localip"), "lan_key": lan_key,
        "sid": dev["mac"].replace(":", "").lower(),
    }


def merge(cloud_devices: list[dict], room_of: dict[str, str], existing: dict[str, dict],
          gateway_id: str, lan_key: str) -> tuple[list[dict], dict]:
    """Return (records, summary). Cloud wins for SYNCED_FIELDS; local 'hidden' is kept;
    local devices missing from the cloud are kept unchanged."""
    gateway_ids = {str(d["did"]) for d in cloud_devices if d.get("model", "").startswith("lumi.gateway")}
    records: dict[str, dict] = {}
    for dev in cloud_devices:
        room = room_of.get(str(dev["did"]), UNASSIGNED)
        if str(dev["did"]) == gateway_id:
            record = gateway_record(dev, room, lan_key)
        else:
            record = convert(dev, gateway_ids, room)
        if record:
            records[record["id"]] = record

    summary = {"added": [], "renamed": [], "moved": [], "token_changed": [], "ip_changed": []}
    for rid, record in records.items():
        old = existing.get(rid)
        if not old:
            summary["added"].append(record["name"])
            continue
        record["hidden"] = old.get("hidden", record["hidden"])
        if old.get("name") != record["name"]:
            summary["renamed"].append(f"{old.get('name')} → {record['name']}")
        if old.get("room") != record["room"]:
            summary["moved"].append(f"{record['name']}：{old.get('room')} → {record['room']}")
        if record.get("token") and old.get("token") != record["token"]:
            summary["token_changed"].append(record["name"])
        if record.get("ip") and old.get("ip") != record["ip"]:
            summary["ip_changed"].append(record["name"])
    for rid, old in existing.items():
        records.setdefault(rid, old)
    return list(records.values()), summary


def rooms_from_homes(homes: list[dict]) -> tuple[dict[str, str], list[str]]:
    room_of, order = {}, []
    for home in homes:
        for room in home["rooms"]:
            order.append(room["name"])
            for did in room["dids"]:
                room_of[did] = room["name"]
    return room_of, order
