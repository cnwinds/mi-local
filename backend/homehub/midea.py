"""One-time setup of Midea appliances: find them on the LAN, fetch their V3 token/key from the Meiju cloud.

The account password is only used for this login and never stored; afterwards the hub talks to the
appliance directly on the LAN.
"""
import logging

import aiohttp
from midealocal.cloud import get_midea_cloud
from midealocal.discover import discover
from msmart.device import AirConditioner

from .catalog import UNASSIGNED

log = logging.getLogger(__name__)

AC_TYPE = 0xAC


async def _working_keys(ip: str, port: int, device_id: int, keys: dict) -> tuple[str, str] | None:
    for method, kv in keys.items():
        ac = AirConditioner(ip=ip, port=port, device_id=device_id)
        try:
            await ac.authenticate(kv["token"], kv["key"])
            await ac.refresh()
            if ac.online:
                return kv["token"], kv["key"]
        except Exception as e:
            log.debug("midea %s key method %s failed: %s", device_id, method, e)
    return None


async def setup(account: str, password: str) -> list[dict]:
    """Return records for every Midea AC on the LAN that the account can unlock."""
    found = {did: d for did, d in (await discover()).items() if d.get("type") == AC_TYPE}
    if not found:
        raise RuntimeError("局域网里没有找到美的空调，请确认空调已通电并连上 Wi-Fi")
    async with aiohttp.ClientSession() as session:
        cloud = get_midea_cloud("美的美居", session, account, password)
        try:
            ok = await cloud.login()
        except Exception as e:
            raise RuntimeError(f"美的美居登录失败：{e}") from None
        if not ok:
            raise RuntimeError("美的美居登录失败，请检查手机号和密码")
        names: dict[int, str] = {}
        try:
            for home_id in await cloud.list_home() or {}:
                for did, info in (await cloud.list_appliances(str(home_id)) or {}).items():
                    names[did] = info.get("name") or ""
        except Exception as e:
            log.debug("midea appliance list failed: %s", e)
        records = []
        for did, dev in found.items():
            ip, port = dev["ip_address"], int(dev.get("port") or 6444)
            record = {
                "id": f"midea.{did}", "name": names.get(did) or "美的空调", "room": UNASSIGNED, "kind": "ac",
                "model": f"midea.ac.{dev.get('sn8') or dev.get('model') or ''}".rstrip("."), "driver": "midea",
                "ip": ip, "port": port, "device_id": str(did), "hidden": False,
            }
            if int(dev.get("protocol") or 3) >= 3:
                try:
                    keys = await cloud.get_cloud_keys(did)
                except Exception as e:
                    log.warning("midea %s key fetch failed: %s", did, e)
                    keys = {}
                pair = await _working_keys(ip, port, did, keys) if keys else None
                if not pair:
                    log.warning("midea %s: no cloud key works (is it bound to this account?)", did)
                    continue
                record["midea_token"], record["midea_key"] = pair
            records.append(record)
    if not records:
        raise RuntimeError("找到了空调，但这个美的美居账号取不到它的密钥。请确认空调已绑定在这个账号下")
    return records
