"""Mi Home cameras, streamed by a local go2rtc (github.com/AlexxIT/go2rtc).

go2rtc holds its own Xiaomi login and speaks the cameras' private P2P protocols. It listens on loopback
only, because its API can rewrite its config and run commands: browsers reach it solely through the
hub's per-camera stream socket, which forwards nothing but the playback requests.
"""
import asyncio
import json
import logging
import os
from urllib.parse import quote

import requests
import websockets
from fastapi import WebSocket, WebSocketDisconnect

from .store import cameras_file

log = logging.getLogger(__name__)

GO2RTC = os.environ.get("HUB_GO2RTC", "http://127.0.0.1:1984")
GO2RTC_WS = "ws" + GO2RTC.removeprefix("http")
CAMERA_HINTS = (".camera.", ".cateye.")
QUALITIES = ("sd", "hd")
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
    return url + "&subtype=sd" if quality == "sd" else url


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
                urls = [p.get("url") for p in (current.get(name) or {}).get("producers") or []]
                if urls == [src]:
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
