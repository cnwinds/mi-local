"""Lockin (鹿客) smart locks through the Lockin / dding cloud, read-only.

Private API of the official app; the request signature was recovered from the Android client
(see github.com/cccmder/ha-lockin-cloud). No unlock, lock or password changes are ever sent.
"""
import asyncio
import hashlib
import logging
import time

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://device-server-2c.dding.net"
SIGN_SECRET = "87f2be668896e243c4c13755b3b9ed9d"
APP_KEY = "8da5ee01647719e67c49d82d"
AUTH_ERRORS = (4007, 14001, 14003, 14008, 1001, 1002)
DOOR_STATES = {1: "open", 2: "closed"}
OPEN_EVENT_IDS = {2203}
SOURCE_METHOD = {1: "密码", 2: "密码", 3: "指纹", 4: "门卡", 5: "钥匙", 6: "手机", 7: "蓝牙钥匙", 8: "人脸",
                 9: "胁迫指纹"}
GATEWAY_MODELS = ("DC-MC02",)


class LockinAuthError(RuntimeError):
    pass


def java_urlencode(value: str) -> str:
    """java.net.URLEncoder.encode(value, "UTF-8"), which the signature is computed over."""
    out = []
    for byte in value.encode("utf-8"):
        char = chr(byte)
        if char.isascii() and (char.isalnum() or char in ".-_*"):
            out.append(char)
        elif char == " ":
            out.append("+")
        else:
            out.append(f"%{byte:02X}")
    return "".join(out)


def build_sign(method: str, path: str, params: dict) -> str:
    raw = (method + path).lower() + "&".join(f"{k}={params[k]}" for k in sorted(params)) + SIGN_SECRET
    return hashlib.md5(java_urlencode(raw).encode("utf-8")).hexdigest()


class LockinCloud:
    def __init__(self, data: dict):
        self.data = data
        self._http = requests.Session()
        self._lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.data.get("access_token"))

    def _get(self, path: str, extra: dict | None = None) -> dict:
        params = {"access_token": self.data["access_token"], "key": APP_KEY, **(extra or {}),
                  "timestamp": str(int(time.time() * 1000))}
        params["sign"] = build_sign("get", path, params)
        resp = self._http.get(BASE_URL + path, params=params, timeout=20)
        resp.raise_for_status()
        body = resp.json()
        err = body.get("ErrNo", 0)
        if err in AUTH_ERRORS:
            raise LockinAuthError(f"鹿客令牌无效或已过期（{err}）")
        if err:
            raise RuntimeError(f"鹿客云返回错误 {err}：{body.get('ErrMsg')}")
        return body

    async def get(self, path: str, extra: dict | None = None) -> dict:
        async with self._lock:
            return await asyncio.to_thread(self._get, path, extra)

    async def locks(self) -> list[dict]:
        """[{uuid, name, model}] for every lock in the account."""
        payload = await self.get("/api/v1/device/")
        devices = payload.get("devices") or []
        with_locker = {s.get("uuid") for s in payload.get("states") or [] if s.get("locker_status")}
        picked = [d for d in devices if d.get("uuid") in with_locker] or [
            d for d in devices if d.get("model") not in GATEWAY_MODELS]
        return [{"uuid": d["uuid"], "model": d.get("model") or "",
                 "name": (d.get("settings") or {}).get("nickname") or d.get("nickname") or "鹿客门锁"} for d in picked]


def describe(detail: dict) -> str:
    who = detail.get("source_name") or detail.get("nickname")
    method = SOURCE_METHOD.get(detail.get("source"))
    if who and method:
        return f"{who}用{method}开锁"
    if who:
        return f"{who}开锁"
    return f"用{method}开锁" if method else "门锁已打开"


class LockinLockDriver:
    """State: door ("open" / "closed"), battery, lock_online, last_event, last_event_ts.
    Emits "unlock" for each new unlock record and "door_open" / "door_close" on door changes."""

    kind = "lock"
    poll_interval = 30.0
    offline_retry = 120.0

    def __init__(self, record: dict, cloud: LockinCloud, on_event):
        self.record = record
        self.cloud = cloud
        self.on_event = on_event
        self.uuid = record["lockin_uuid"]
        self._last_record: int | None = None
        self._door: str | None = None

    async def poll(self) -> dict:
        info = await self.cloud.get("/api/lock/v1/info", {"uuid": self.uuid})
        device = info.get("device") or {}
        locker = device.get("locker_status") or {}
        state = {
            "door": DOOR_STATES.get(locker.get("doorstate")),
            "battery": device.get("power"),
            "lock_online": device.get("onoff_line") == 1,
        }
        try:
            records = await self.cloud.get("/api/v1/safety/family_record")
        except LockinAuthError:
            raise
        except Exception as e:
            log.debug("lockin records failed: %s", e)
            records = {}
        mine = sorted((r for r in records.get("family_record") or [] if r.get("uuid") == self.uuid),
                      key=lambda r: r.get("time") or 0)
        opens = [r for r in mine if r.get("eventid") in OPEN_EVENT_IDS]
        if opens:
            latest = opens[-1]
            state["last_event"] = describe(latest.get("detail") or {})
            state["last_event_ts"] = (latest.get("time") or 0) / 1000
        if mine:
            newest = mine[-1].get("time") or 0
            if self._last_record is not None:
                for r in opens:
                    if (r.get("time") or 0) > self._last_record:
                        self.on_event("unlock")
            self._last_record = max(self._last_record or 0, newest)
        elif self._last_record is None:
            self._last_record = 0
        door = state["door"]
        if self._door and door and door != self._door:
            self.on_event("door_open" if door == "open" else "door_close")
        self._door = door or self._door
        return state

    async def command(self, action: str, value=None) -> None:
        raise ValueError("门锁只读，不支持远程操作")
