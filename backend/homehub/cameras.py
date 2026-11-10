"""Mi Home cameras, streamed by a local go2rtc (github.com/AlexxIT/go2rtc).

go2rtc holds its own Xiaomi login and speaks the cameras' private P2P protocols. It listens on loopback
only, because its API can rewrite its config and run commands: browsers reach it solely through the
hub's per-camera stream socket, which forwards nothing but the playback requests.
"""
import asyncio
import json
import logging
import os
import re
from urllib.parse import quote

import requests
import websockets
from fastapi import WebSocket, WebSocketDisconnect

from .store import cameras_file

log = logging.getLogger(__name__)

GO2RTC = os.environ.get("HUB_GO2RTC", "http://127.0.0.1:1984")
GO2RTC_WS = "ws" + GO2RTC.removeprefix("http")
CAMERA_HINTS = (".camera.", ".cateye.")
# "hd3" is the MISS quality level 3: some models keep their HD stream there and never answer level 2.
QUALITIES = ("sd", "hd", "hd3")
SUBTYPES = {"sd": "sd", "hd3": "3"}
# Browser -> go2rtc messages that only start playback; offers for other transports are dropped.
CLIENT_TYPES = {"mse", "mjpeg"}
LOCAL_FIELDS = ("hidden", "unsupported")
# go2rtc's answer for models whose P2P vendor it cannot speak; retrying will not change it.
UNSUPPORTED = "unsupported model"


def is_camera(model: str) -> bool:
    return any(hint in model for hint in CAMERA_HINTS)


def from_homes(homes: list[dict], room_of: dict[str, str], existing: list[dict], unassigned: str) -> list[dict]:
    old = {c["id"]: c for c in existing}
    cameras = []
    for dev in (d for h in homes for d in h["devices"]):
        if not is_camera(dev.get("model", "")) or not dev.get("localip"):
            continue
        cid = str(dev["did"])
        camera = {"id": cid, "name": dev.get("name") or dev["model"], "room": room_of.get(cid, unassigned),
                  "model": dev["model"], "ip": dev["localip"], "hidden": False}
        camera.update({f: old[cid][f] for f in LOCAL_FIELDS if f in old.get(cid, {})})
        cameras.append(camera)
    return cameras


def stream_name(camera_id: str, quality: str) -> str:
    return f"cam_{camera_id}_{quality}"


def source(camera: dict, user_id: str, quality: str) -> str:
    url = f"xiaomi://{user_id}:cn@{camera['ip']}?did={camera['id']}&model={camera['model']}"
    return f"{url}&subtype={SUBTYPES[quality]}" if quality in SUBTYPES else url


def go2rtc_accounts() -> list[str] | None:
    """Xiaomi user IDs go2rtc is logged in with; None when go2rtc isn't running."""
    try:
        resp = requests.get(f"{GO2RTC}/api/xiaomi", timeout=5)
        resp.raise_for_status()
        return [str(u) for u in resp.json() or []]
    except (requests.RequestException, ValueError):
        return None


def go2rtc_login(fields: dict[str, str]) -> dict:
    """One step of go2rtc's own Xiaomi login: {"username", "password"}, then {"captcha"} or {"verify"} if asked.

    The only go2rtc endpoint the hub passes anything to; the password is forwarded once and never kept.
    Returns {"ok": True}, {"captcha": base64 image} or {"verify": masked phone or email}.
    """
    resp = requests.post(f"{GO2RTC}/api/xiaomi", data=fields, timeout=30)
    if resp.status_code == 401:
        step = resp.json()
        if step.get("captcha"):
            return {"captcha": step["captcha"]}
        return {"verify": step.get("verify_phone") or step.get("verify_email") or "你的手机或邮箱"}
    if not resp.ok:
        text = resp.text.strip()
        if "70016" in text:
            raise ValueError("账号或密码不对")
        raise ValueError(f"小米账号登录失败：{text[:160] or resp.reason}")
    return {"ok": True}


def masked(url: str) -> str:
    """go2rtc hides the account part of source URLs in its API; compare ours the same way."""
    return re.sub(r"^(\w+://)[^@/]*@", r"\1***@", url)


class Cameras:
    def __init__(self):
        self.items: list[dict] = cameras_file.load()

    def get(self, camera_id: str) -> dict | None:
        return next((c for c in self.items if c["id"] == camera_id), None)

    def public(self) -> list[dict]:
        return [{**{k: c[k] for k in ("id", "name", "room", "model", "hidden")},
                 "unsupported": c.get("unsupported", False)} for c in self.items]

    def update(self, camera_id: str, **fields: bool) -> dict:
        camera = self.get(camera_id)
        if not camera:
            raise KeyError(camera_id)
        camera.update(fields)
        cameras_file.save(self.items)
        return camera

    async def sync(self, homes: list[dict], room_of: dict[str, str], user_id: str, unassigned: str) -> None:
        cameras = from_homes(homes, room_of, self.items, unassigned)
        if cameras != self.items:
            self.items = cameras
            cameras_file.save(cameras)
        try:
            await asyncio.to_thread(self._register, user_id)
        except requests.RequestException as e:
            log.info("go2rtc not reachable, camera streams not registered: %s", e)

    def _register(self, user_id: str) -> None:
        """Point go2rtc's streams at the cameras' current addresses (they move when DHCP does)."""
        current = requests.get(f"{GO2RTC}/api/streams", timeout=5).json() or {}
        for camera in self.items:
            for quality in QUALITIES:
                name, src = stream_name(camera["id"], quality), source(camera, user_id, quality)
                urls = [masked(p.get("url", "")) for p in (current.get(name) or {}).get("producers") or []]
                if urls == [masked(src)]:
                    continue
                method = "PATCH" if name in current else "PUT"
                requests.request(method, f"{GO2RTC}/api/streams", params={"name": name, "src": src},
                                 timeout=5).raise_for_status()
                log.info("go2rtc stream %s -> %s", name, camera["ip"])


async def relay(client: WebSocket, stream: str, on_unsupported) -> None:
    """Pipe one browser player socket to go2rtc's stream socket until either side closes."""
    try:
        async with websockets.connect(f"{GO2RTC_WS}/api/ws?src={quote(stream)}", max_size=None,
                                      open_timeout=10) as upstream:
            async def down():
                async for message in upstream:
                    if isinstance(message, bytes):
                        await client.send_bytes(message)
                        continue
                    if UNSUPPORTED in message:
                        on_unsupported()
                    await client.send_text(message)

            async def up():
                while True:
                    text = await client.receive_text()
                    try:
                        kind = json.loads(text).get("type")
                    except (ValueError, AttributeError):
                        continue
                    if kind in CLIENT_TYPES:
                        await upstream.send(text)

            tasks = [asyncio.create_task(down()), asyncio.create_task(up())]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    except (OSError, asyncio.TimeoutError, websockets.WebSocketException):
        try:
            await client.send_text(json.dumps({"type": "error", "value": "unavailable: 监控服务没有运行"}))
        except (RuntimeError, WebSocketDisconnect):
            pass
    except WebSocketDisconnect:
        pass
