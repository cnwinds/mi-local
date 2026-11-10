"""Map Mi Home cloud devices to local device records and merge them into the existing set.

Known models get their dedicated drivers. Anything else is typed by its MIoT spec (a light, an AC…) and runs on the
generic spec driver: over miIO when it has a LAN address, otherwise ("miot_cloud") through the Mi Home cloud.
"""
import ipaddress

from .drivers.miot_typed import KIND_BY_TYPE

UNASSIGNED = "未分配"
LIGHT_DRIVERS = {"yeelink.light.ceiling": "yeelight", "philips.light.downlight": "philips"}
GW2_KINDS = {"lumi.sensor_switch.v2": "switch", "lumi.plug.v1": "plug", "lumi.curtain.v1": "curtain"}
# Cameras are picked up by cameras.py and streamed through go2rtc instead. miir.* are virtual infrared remotes:
# they only take MIoT actions, which the spec driver doesn't send yet.
SKIP_MODELS = (".camera.", ".cateye.", "miir.")
# Network gear, not something to switch from a home panel.
SKIP_SPEC_TYPES = {"router", "gateway"}
PRIVATE_NETS = tuple(ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
# These refuse LAN control or sit on a subnet the hub cannot reach; they go through the Mi Home cloud.
CLOUD_KINDS = {"xiaomi.aircondition.ma2": "ac", "lumi.acpartner.v2": "ac", "viomi.bhf_light.v1": "bath_heater",
               "mrbond.airer.m1pro": "airer"}
SYNCED_FIELDS = ("name", "room", "model", "ip", "token")
# Set in this app only; Mi Home cannot be written back to with our session.
LOCAL_FIELDS = ("hidden", "local_name", "local_room", "name_auto", "ip_override")


def is_lan_ip(ip: str) -> bool:
    try:
        return any(ipaddress.ip_address(ip) in net for net in PRIVATE_NETS)
    except ValueError:
        return False


def convert(dev: dict, gateway_ids: set[str], room: str, spec_type: str | None = None) -> dict | None:
    """spec_type: the model's MIoT device type ("light"…), None when it has no spec or the index was unreachable."""
    model = dev.get("model", "")
    base = {"id": str(dev["did"]), "name": dev.get("name", model), "room": room, "model": model, "hidden": False}
    # Zigbee devices still on the multimode gateway are mapped to Gateway 2 too: they show
    # offline until re-paired to Gateway 2, which keeps the same Zigbee address.
    if model in GW2_KINDS and str(dev.get("parent_id")) in gateway_ids:
        sid = str(dev["did"]).removeprefix("lumi.")
        kind = GW2_KINDS[model]
        return {**base, "id": f"lumi.{sid}", "kind": kind, "driver": "gw2", "sid": sid, "gw_model": kind}
    if model in CLOUD_KINDS:
        return {**base, "kind": CLOUD_KINDS[model], "driver": "cloud"}
    if model.startswith("lumi.gateway") or any(s in model for s in SKIP_MODELS):
        return None
    ip, token = dev.get("localip") or "", dev.get("token")
    lan = bool(token) and is_lan_ip(ip)
    if lan:
        for prefix, driver in LIGHT_DRIVERS.items():
            if model.startswith(prefix):
                return {**base, "kind": "light", "driver": driver, "ip": ip, "token": token}
    kind = KIND_BY_TYPE.get(spec_type or "", "other")
    hidden = not dev.get("isOnline")
    if lan:
        return {**base, "kind": kind, "driver": "miio", "ip": ip, "token": token, "hidden": hidden}
    # No LAN address (Bluetooth Mesh, Zigbee on a multimode gateway…): the cloud is the only way in, so only
    # devices whose spec tells us what they can do are worth importing. Those without a tile start hidden:
    # kettles and sensors would otherwise crowd the home page.
    if spec_type and spec_type not in SKIP_SPEC_TYPES:
        return {**base, "kind": kind, "driver": "miot_cloud", "hidden": hidden or kind == "other"}
    return None


def gateway_record(dev: dict, room: str, lan_key: str, ip: str | None = None) -> dict:
    return {
        "id": str(dev["did"]), "name": dev.get("name", "网关"), "room": room, "kind": "gateway",
        "model": dev["model"], "hidden": True, "ip": ip or dev.get("localip"), "lan_key": lan_key,
        "token": dev.get("token"),
        "sid": dev["mac"].replace(":", "").lower(),
    }


def merge(cloud_devices: list[dict], room_of: dict[str, str], existing: dict[str, dict],
          gateway_id: str, lan_key: str, spec_types: dict[str, str] | None = None) -> tuple[list[dict], dict]:
    """Return (records, summary). Cloud wins for SYNCED_FIELDS; LOCAL_FIELDS are kept;
    local devices missing from the cloud are kept unchanged. spec_types: model -> MIoT device type."""
    spec_types = spec_types or {}
    gateway_ids = {str(d["did"]) for d in cloud_devices if d.get("model", "").startswith("lumi.gateway")}
    records: dict[str, dict] = {}
    for dev in cloud_devices:
        room = room_of.get(str(dev["did"]), UNASSIGNED)
        if str(dev["did"]) == gateway_id:
            record = gateway_record(dev, room, lan_key)
        else:
            record = convert(dev, gateway_ids, room, spec_types.get(dev.get("model", "")))
        if record:
            records[record["id"]] = record

    summary = {"added": [], "renamed": [], "moved": [], "token_changed": [], "ip_changed": []}
    for rid, record in records.items():
        old = existing.get(rid)
        if not old:
            summary["added"].append(record["name"])
            continue
        record.update({f: old[f] for f in LOCAL_FIELDS if f in old})
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
