"""Let Xiao Ai speakers control devices Mi Home does not know about.

The speakers upload every utterance to the Xiao Ai cloud; we poll each speaker's conversation log, and
when a query names one of our non-Mi devices we run the command and answer through the speaker.
"""
import asyncio
import base64
import hashlib
import json
import logging
import re
import time
import urllib.parse
import uuid

import requests

from .drivers.miot_transport import cloud_call

log = logging.getLogger(__name__)

VOICE_DRIVERS = ("midea",)
POLL_INTERVAL = 1.5
SPEAKER_REFRESH = 600
UA = ("MiHome/6.0.103 (com.xiaomi.mihome; build:6.0.103.1; iOS 14.4.0) Alamofire/6.0.103 "
      "MICO/iOSApp/appStore/6.0.103")
# Speakers whose MIoT "play-text" action (siid, aiid) reads text aloud; others use the mina ubus call.
TTS_ACTIONS = {"LX06": (5, 1), "S12": (5, 1), "S12A": (5, 1), "LX01": (5, 1), "L06A": (5, 1), "LX04": (5, 1),
               "L05B": (5, 3), "L05C": (5, 3), "L17A": (7, 3), "X08E": (7, 3), "LX05": (5, 1), "L15A": (7, 3)}

MODE_WORDS = {"制冷": "cool", "冷风": "cool", "制热": "heat", "暖风": "heat", "热风": "heat", "除湿": "dry",
              "抽湿": "dry", "送风": "fan", "通风": "fan", "自动": "auto"}
MODE_ZH = {"cool": "制冷", "heat": "制热", "dry": "除湿", "fan": "送风", "auto": "自动"}
CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn_number(text: str) -> float | None:
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)
    if not text or any(c not in CN_DIGITS and c != "十" for c in text):
        return None
    if "十" not in text:
        return float(CN_DIGITS[text]) if len(text) == 1 else None
    tens, _, ones = text.partition("十")
    return float((CN_DIGITS.get(tens, 1) if tens else 1) * 10 + (CN_DIGITS.get(ones, 0) if ones else 0))


def normalize(text: str) -> str:
    return re.sub(r"[\s的，。,.！!？?]", "", text)


def parse(query: str, devices: dict[str, str]) -> tuple[str, list[tuple[str, object]], str] | None:
    """devices: id -> name. Returns (device_id, [(action, value)], reply) when the query targets one of them."""
    q = normalize(query)
    for device_id, name in sorted(devices.items(), key=lambda kv: -len(kv[1])):
        target = normalize(name)
        if not target or target not in q:
            continue
        rest = q.replace(target, " ")
        actions, said = [], []
        if re.search(r"关[闭掉上了]?|停", rest):
            return device_id, [("turn_off", None)], f"好的，{name}已关闭"
        if "开" in rest:
            actions.append(("turn_on", None))
            said.append("已打开")
        mode = next((m for w, m in MODE_WORDS.items() if w in rest), None)
        if mode:
            actions.append(("set_mode", mode))
            said.append(f"{MODE_ZH[mode]}模式")
        m = re.search(r"([\d.]+|[零一二两三四五六七八九十]+)度", rest)
        temp = cn_number(m.group(1)) if m else None
        if temp is not None and 16 <= temp <= 32:
            actions.append(("set_temp", temp))
            said.append(f"{temp:g}度")
        elif re.search(r"调高|升高|高一点|热一点", rest):
            actions.append(("temp_delta", 1))
            said.append("温度调高了")
        elif re.search(r"调低|降低|低一点|冷一点", rest):
            actions.append(("temp_delta", -1))
            said.append("温度调低了")
        if actions:
            return device_id, actions, f"好的，{name}" + "，".join(said)
    return None


class Mina:
    """Minimal Xiao Ai (micoapi) client riding on the Mi Home login's passToken."""

    def __init__(self, cloud_data: dict):
        self.cloud_data = cloud_data
        self.session = requests.Session()
        self.token: str | None = None

    def login(self) -> None:
        s = self.session
        resp = s.get("https://account.xiaomi.com/pass/serviceLogin?sid=micoapi&_json=true", timeout=10,
                     cookies={"userId": str(self.cloud_data["user_id"]), "passToken": self.cloud_data["pass_token"]})
        body = json.loads(resp.text.replace("&&&START&&&", ""))
        if not body.get("location"):
            raise RuntimeError(f"小爱服务登录失败（{body.get('code')}）")
        sign = base64.b64encode(hashlib.sha1(f"nonce={body['nonce']}&{body['ssecurity']}".encode()).digest()).decode()
        r = s.get(body["location"] + "&clientSign=" + urllib.parse.quote(sign), timeout=10)
        self.token = s.cookies.get("serviceToken") or r.cookies.get("serviceToken")
        if not self.token:
            raise RuntimeError("小爱服务没有返回登录凭据")

    def _request(self, method: str, url: str, device_id: str | None = None, **kwargs) -> dict:
        if not self.token:
            self.login()
        cookies = {"userId": str(self.cloud_data["user_id"]), "serviceToken": self.token}
        if device_id:
            cookies["deviceId"] = device_id
        r = self.session.request(method, url, cookies=cookies, headers={"User-Agent": UA}, timeout=10, **kwargs)
        if r.status_code == 401:
            self.token = None
            raise RuntimeError("小爱服务凭据过期")
        return r.json()

    def speakers(self) -> list[dict]:
        return self._request("GET", "https://api2.mina.mi.com/admin/v2/device_list?master=0").get("data") or []

    def conversations(self, speaker: dict, limit: int = 2) -> list[dict]:
        body = self._request("GET", "https://userprofile.mina.mi.com/device_profile/v2/conversation",
                             device_id=speaker["deviceID"],
                             params={"source": "dialogu", "hardware": speaker["hardware"],
                                     "timestamp": int(time.time() * 1000), "limit": limit})
        return json.loads(body.get("data") or "{}").get("records") or []

    def ubus(self, speaker: dict, path: str, method: str, message: dict) -> dict:
        return self._request("POST", "https://api2.mina.mi.com/remote/ubus", data={
            "deviceId": speaker["deviceID"], "path": path, "method": method,
            "message": json.dumps(message, ensure_ascii=False), "requestId": uuid.uuid4().hex})

    def stop(self, speaker: dict) -> None:
        self.ubus(speaker, "mediaplayer", "player_play_operation", {"action": "stop", "media": "app_ios"})


class VoiceBridge:
    def __init__(self, hub):
        self.hub = hub
        self.mina: Mina | None = None
        self.speakers: list[dict] = []
        self._speakers_at = 0.0
        self._last: dict[str, int] = {}
        self.status: dict = {"active": False, "error": None, "last": None}

    def targets(self) -> dict[str, str]:
        return {rid: self.hub.public_device(rid)["name"] for rid, r in self.hub.records.items()
                if r.get("driver") in VOICE_DRIVERS}

    def public_status(self) -> dict:
        return {**self.status, "enabled": self.hub.settings.get("voice_bridge", True),
                "devices": list(self.targets().values()),
                "speakers": [{"name": s.get("name"), "online": s.get("presence") == "online"} for s in self.speakers]}

    def _set(self, **changes) -> None:
        if any(self.status.get(k) != v for k, v in changes.items()):
            self.status.update(changes)
            self.hub.broadcast({"type": "voice"})

    async def run(self) -> None:
        while True:
            try:
                if not (self.hub.cloud.logged_in and self.hub.settings.get("voice_bridge", True) and self.targets()):
                    self._set(active=False)
                    await asyncio.sleep(10)
                    continue
                await self._cycle()
                self._set(active=True, error=None)
                await asyncio.sleep(POLL_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("voice bridge: %s", e)
                self._set(active=False, error=str(e))
                await asyncio.sleep(30)

    async def _cycle(self) -> None:
        if self.mina is None or self.mina.cloud_data is not self.hub.cloud.data:
            self.mina = Mina(self.hub.cloud.data)
        if time.time() - self._speakers_at > SPEAKER_REFRESH:
            self.speakers = await asyncio.to_thread(self.mina.speakers)
            self._speakers_at = time.time()
            self.hub.broadcast({"type": "voice"})
        for speaker in self.speakers:
            if speaker.get("presence") != "online":
                continue
            records = await asyncio.to_thread(self.mina.conversations, speaker)
            sid = speaker["deviceID"]
            newest = max((r["time"] for r in records), default=0)
            if sid not in self._last:
                self._last[sid] = newest
                continue
            for rec in sorted(records, key=lambda r: r["time"]):
                if rec["time"] > self._last[sid] and rec.get("query"):
                    await self._handle(speaker, rec["query"])
            self._last[sid] = max(self._last[sid], newest)

    async def _handle(self, speaker: dict, query: str) -> None:
        parsed = parse(query, self.targets())
        if not parsed:
            return
        device_id, actions, reply = parsed
        log.info("voice: %s heard %r -> %s %s", speaker.get("name"), query, device_id, actions)
        try:
            await asyncio.to_thread(self.mina.stop, speaker)
        except Exception as e:
            log.debug("stop speaker failed: %s", e)
        try:
            for action, value in actions:
                if action == "temp_delta":
                    state = self.hub.states.get(device_id, {})
                    action, value = "set_temp", float(state.get("target_temp") or 26) + value
                await self.hub.command(device_id, action, value)
        except Exception as e:
            log.warning("voice command for %s failed: %s", device_id, e)
            reply = "抱歉，" + self.hub.public_device(device_id)["name"] + "没有响应"
        await self.say(speaker, reply)
        self._set(last={"ts": time.time(), "speaker": speaker.get("name"), "query": query, "reply": reply})

    async def say(self, speaker: dict, text: str) -> None:
        action = TTS_ACTIONS.get(speaker.get("hardware", ""))
        if action and speaker.get("miotDID"):
            try:
                result = await cloud_call(self.hub.cloud, "/miotspec/action", {"params": {
                    "did": str(speaker["miotDID"]), "siid": action[0], "aiid": action[1], "in": [text]}})
                if result.get("code", 0) == 0:
                    return
                log.debug("play-text on %s returned %s", speaker.get("name"), result.get("code"))
            except Exception as e:
                log.debug("play-text on %s failed: %s", speaker.get("name"), e)
        await asyncio.to_thread(self.mina.ubus, speaker, "mibrain", "text_to_speech", {"text": text})
