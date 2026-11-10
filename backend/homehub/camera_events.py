"""Motion events the cameras upload to the Mi Home cloud (看家): the event list, thumbnails and clips.

Thumbnails and clip segments come AES-encrypted from signed cloud URLs that embed the account session.
The hub fetches and decrypts them itself, so none of those URLs ever reaches a browser.
"""
import base64
import os
import re
import threading
import time
from collections import OrderedDict

from Crypto.Cipher import AES

from .micloud import MiCloud

EVENTS_URL = "https://business.smartcamera.api.io.mi.com/common/app/get/eventlist"
M3U8_URL = "https://business.smartcamera.api.io.mi.com/common/app/m3u8"
IMG_URL = "https://processor.smartcamera.api.io.mi.com/miot/camera/app/v1/img"
KEY_RE = re.compile(r'#EXT-X-KEY:METHOD=AES-128,URI="([^"]+)",IV=0x([0-9A-Fa-f]{32})')
SEGMENT_RE = re.compile(r"^(https://\S+)$", re.M)
DURATION_RE = re.compile(r"^#EXTINF:([\d.]+)", re.M)
# The cloud keeps free events a week and paid plans up to a month; look back far enough for either.
LOOKBACK_MS = 31 * 86400 * 1000
PLAYLIST_TTL = 300
MEDIA_CACHE_BYTES = 64 * 1024 * 1024
# eventType holds every detector that fired, e.g. "ObjectMotion:PeopleMotion"; the most specific wins.
KINDS = (("PeopleMotion", "person"), ("Face", "face"), ("BabyCry", "cry"), ("Pet", "pet"),
         ("LouderSound", "sound"), ("ObjectMotion", "motion"))


def kind_of(event_type: str) -> str:
    return next((kind for marker, kind in KINDS if marker in event_type), "other")


def decrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    plain = AES.new(key, AES.MODE_CBC, iv).decrypt(data[: len(data) // 16 * 16])
    pad = plain[-1] if plain else 0
    return plain[:-pad] if 0 < pad <= 16 and plain.endswith(bytes([pad]) * pad) else plain


def parse_playlist(text: str) -> dict:
    key = KEY_RE.search(text)
    segments = SEGMENT_RE.findall(text)
    if not key or not segments:
        raise ValueError("unexpected clip playlist")
    return {"key_url": key.group(1), "iv": bytes.fromhex(key.group(2)), "segments": segments,
            "durations": [float(d) for d in DURATION_RE.findall(text)]}


class CameraEvents:
    def __init__(self, cloud: MiCloud):
        self.cloud = cloud
        self._lock = threading.Lock()
        self._units: OrderedDict[str, dict] = OrderedDict()
        self._playlists: dict[str, dict] = {}
        self._media: OrderedDict[str, bytes] = OrderedDict()
        self._media_bytes = 0

    def list(self, camera: dict, before_ms: int | None, limit: int) -> dict:
        end = before_ms or int(time.time() * 1000)
        data = self.cloud.camera_api(EVENTS_URL, {
            "did": camera["id"], "model": camera["model"], "doorBell": False, "eventType": "Default",
            "needMerge": True, "sortType": "DESC", "region": "CN", "language": "zh_CN",
            "beginTime": end - LOOKBACK_MS, "endTime": end, "limit": limit,
        })
        units = data.get("thirdPartPlayUnits") or []
        with self._lock:
            for unit in units:
                self._units[unit["fileId"]] = {**unit, "did": camera["id"]}
                self._units.move_to_end(unit["fileId"])
            while len(self._units) > 5000:
                self._units.popitem(last=False)
        return {
            "items": [{"id": u["fileId"], "time": u["createTime"] / 1000, "kind": kind_of(u.get("eventType", "")),
                       "duration": u.get("duration") or 0} for u in units],
            # The cloud may return a short page and still have more; an empty page always ends the list.
            "more": bool(data.get("isContinue")) and bool(units),
        }

    def _unit(self, camera: dict, file_id: str) -> dict:
        unit = self._units.get(file_id)
        if not unit or unit["did"] != camera["id"]:
            raise KeyError(file_id)
        return unit

    def thumbnail(self, camera: dict, file_id: str) -> bytes:
        cache_key = f"img:{file_id}"
        if cached := self._cached(cache_key):
            return cached
        unit = self._unit(camera, file_id)
        iv = os.urandom(16)
        raw = self.cloud.camera_fetch(IMG_URL, {"did": camera["id"], "fileId": file_id, "stoId": unit.get("imgStoreId"),
                                                "segmentIv": base64.b64encode(iv).decode()})
        image = decrypt(raw, base64.b64decode(self.cloud.data["ssecurity"]), iv)
        self._store(cache_key, image)
        return image

    def _playlist(self, camera: dict, file_id: str) -> dict:
        playlist = self._playlists.get(file_id)
        if playlist and time.time() - playlist["at"] < PLAYLIST_TTL:
            return playlist
        unit = self._unit(camera, file_id)
        text = self.cloud.camera_fetch(M3U8_URL, {"did": camera["id"], "model": camera["model"], "fileId": file_id,
                                                  "isAlarm": bool(unit.get("isAlarm", True)), "videoCodec": "H265"})
        playlist = {**parse_playlist(text.decode()), "at": time.time()}
        with self._lock:
            self._playlists = {k: v for k, v in self._playlists.items() if time.time() - v["at"] < PLAYLIST_TTL}
            self._playlists[file_id] = playlist
        return playlist

    def clip(self, camera: dict, file_id: str) -> dict:
        playlist = self._playlist(camera, file_id)
        return {"parts": playlist["durations"] or [0.0] * len(playlist["segments"])}

    def clip_part(self, camera: dict, file_id: str, index: int) -> bytes:
        cache_key = f"clip:{file_id}:{index}"
        if cached := self._cached(cache_key):
            return cached
        playlist = self._playlist(camera, file_id)
        if not 0 <= index < len(playlist["segments"]):
            raise KeyError(index)
        key = self.cloud.camera_fetch(playlist["key_url"])
        video = decrypt(self.cloud.camera_fetch(playlist["segments"][index]), key, playlist["iv"])
        self._store(cache_key, video)
        return video

    def _cached(self, key: str) -> bytes | None:
        with self._lock:
            data = self._media.get(key)
            if data is not None:
                self._media.move_to_end(key)
            return data

    def _store(self, key: str, data: bytes) -> None:
        with self._lock:
            if key in self._media:
                return
            self._media[key] = data
            self._media_bytes += len(data)
            while self._media_bytes > MEDIA_CACHE_BYTES and len(self._media) > 1:
                _, old = self._media.popitem(last=False)
                self._media_bytes -= len(old)
