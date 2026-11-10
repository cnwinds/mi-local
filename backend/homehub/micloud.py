"""Minimal Xiaomi cloud client: QR login, session renewal and device/room listing.

Protocol follows PiotrMachowski/Xiaomi-cloud-tokens-extractor (MIT).
"""
import base64
import hashlib
import json
import os
import random
import time
from urllib.parse import urlparse

import requests
from Crypto.Cipher import ARC4

API = "https://api.io.mi.com/app"
SERVICE_LOGIN = "https://account.xiaomi.com/pass/serviceLogin?sid=xiaomiio&_json=true"


class CloudError(Exception):
    pass


def _json(text: str) -> dict:
    return json.loads(text.replace("&&&START&&&", ""))


def _rc4(key_b64: str, payload: bytes) -> bytes:
    cipher = ARC4.new(base64.b64decode(key_b64))
    cipher.encrypt(bytes(1024))
    return cipher.encrypt(payload)


def _signed_nonce(ssecurity: str, nonce: str) -> str:
    return base64.b64encode(hashlib.sha256(base64.b64decode(ssecurity) + base64.b64decode(nonce)).digest()).decode()


def _enc_signature(path: str, signed_nonce: str, params: dict, method: str = "POST") -> str:
    parts = [method, path, *(f"{k}={v}" for k, v in params.items()), signed_nonce]
    return base64.b64encode(hashlib.sha1("&".join(parts).encode()).digest()).decode()


class MiCloud:
    def __init__(self, session_data: dict | None = None):
        self.data = dict(session_data or {})
        rand = "".join(chr(random.randint(97, 122)) for _ in range(18))
        self._agent = f"{rand}-{''.join(chr(random.randint(65, 69)) for _ in range(13))} APP/com.xiaomi.mihome APPV/10.5.201"
        self._http = requests.Session()
        self._lp_url: str | None = None
        self._lp_deadline = 0.0

    @property
    def logged_in(self) -> bool:
        return bool(self.data.get("service_token"))

    @property
    def login_pending(self) -> bool:
        return self._lp_url is not None and time.time() < self._lp_deadline - 30

    # --- QR login -------------------------------------------------------
    def start_qr_login(self) -> dict:
        resp = self._http.get("https://account.xiaomi.com/longPolling/loginUrl", params={
            "_qrsize": "480", "qs": "%3Fsid%3Dxiaomiio%26_json%3Dtrue", "callback": "https://sts.api.io.mi.com/sts",
            "_hasLogo": "false", "sid": "xiaomiio", "serviceParam": "", "_locale": "zh_CN",
            "_dc": str(int(time.time() * 1000)),
        }, timeout=10)
        data = _json(resp.text)
        if "qr" not in data:
            raise CloudError(f"cannot start QR login: {data}")
        self._lp_url = data["lp"]
        self._lp_deadline = time.time() + float(data.get("timeout", 300))
        return {"qr_url": data["qr"], "login_url": data["loginUrl"], "timeout": data.get("timeout", 300)}

    def wait_qr_login(self) -> bool:
        """Blocks until the QR code is scanned (True) or expires (False)."""
        while time.time() < self._lp_deadline:
            try:
                resp = self._http.get(self._lp_url, timeout=10)
            except requests.exceptions.Timeout:
                continue
            if resp.status_code == 200:
                self._lp_url = None
                data = _json(resp.text)
                self.data.update(user_id=str(data["userId"]), pass_token=data["passToken"])
                self._finish_login(data["ssecurity"], data["location"])
                return True
        return False

    def _finish_login(self, ssecurity: str, location: str) -> None:
        resp = self._http.get(location, timeout=10)
        token = resp.cookies.get("serviceToken")
        if not token:
            raise CloudError("no serviceToken in login response")
        self.data.update(ssecurity=ssecurity, service_token=token, login_at=time.time())

    def renew(self) -> None:
        """Get a fresh serviceToken with the stored passToken (no user interaction)."""
        if not self.data.get("pass_token"):
            raise CloudError("not logged in")
        resp = self._http.get(SERVICE_LOGIN, headers={"User-Agent": self._agent},
                              cookies={"userId": self.data["user_id"], "passToken": self.data["pass_token"]}, timeout=10)
        data = _json(resp.text)
        if not data.get("ssecurity") or not data.get("location"):
            self.data.pop("service_token", None)
            raise CloudError("session expired, scan QR code again")
        if data.get("passToken"):
            self.data["pass_token"] = data["passToken"]
        self._finish_login(data["ssecurity"], data["location"])

    # --- API ------------------------------------------------------------
    def _rc4_params(self, path: str, payload: dict, method: str) -> tuple[dict, str]:
        """Encrypted request parameters, and the signed nonce that decrypts the reply."""
        ssecurity = self.data["ssecurity"]
        millis = int(time.time() * 1000)
        nonce = base64.b64encode(os.urandom(8) + (millis // 60000).to_bytes(4, "big")).decode()
        signed = _signed_nonce(ssecurity, nonce)
        params = {"data": json.dumps(payload, separators=(",", ":") if method == "GET" else None)}
        params["rc4_hash__"] = _enc_signature(path, signed, params, method)
        params = {k: base64.b64encode(_rc4(signed, v.encode())).decode() for k, v in params.items()}
        params.update(signature=_enc_signature(path, signed, params, method), ssecurity=ssecurity, _nonce=nonce)
        return params, signed

    @property
    def _cookies(self) -> dict:
        return {"userId": self.data["user_id"], "serviceToken": self.data["service_token"],
                "yetAnotherServiceToken": self.data["service_token"], "locale": "zh_CN", "channel": "MI_APP_STORE"}

    def call(self, path: str, payload: dict, _retry=True) -> dict:
        if not self.logged_in:
            raise CloudError("not logged in")
        params, signed = self._rc4_params(path, payload, "POST")
        resp = self._http.post(API + path, params=params, timeout=15, headers={
            "Accept-Encoding": "identity", "User-Agent": self._agent,
            "Content-Type": "application/x-www-form-urlencoded",
            "x-xiaomi-protocal-flag-cli": "PROTOCAL-HTTP2", "MIOT-ENCRYPT-ALGORITHM": "ENCRYPT-RC4",
        }, cookies=self._cookies)
        if resp.status_code in (401, 403) and _retry:
            self.renew()
            return self.call(path, payload, _retry=False)
        if resp.status_code != 200:
            raise CloudError(f"HTTP {resp.status_code}")
        result = json.loads(_rc4(signed, base64.b64decode(resp.text)))
        if result.get("code") not in (0, None):
            if _retry and result.get("code") in (2, 3):
                self.renew()
                return self.call(path, payload, _retry=False)
            raise CloudError(f"API error {result.get('code')}: {result.get('message')}")
        return result["result"]

    # --- camera services (business/processor.smartcamera.api.io.mi.com) ---------------------
    def camera_api(self, url: str, payload: dict, _retry=True) -> dict:
        """Signed GET to a camera service; replies come RC4-encrypted like the main API."""
        if not self.logged_in:
            raise CloudError("not logged in")
        params, signed = self._rc4_params(urlparse(url).path, payload, "GET")
        resp = self._http.get(url, params=params, cookies=self._cookies, timeout=20,
                              headers={"MIOT-ENCRYPT-ALGORITHM": "ENCRYPT-RC4", "Accept-Encoding": "identity"})
        if resp.status_code in (401, 403) and _retry:
            self.renew()
            return self.camera_api(url, payload, _retry=False)
        if resp.status_code != 200:
            raise CloudError(f"HTTP {resp.status_code}")
        result = json.loads(resp.text) if '"message"' in resp.text[:200] else json.loads(
            _rc4(signed, base64.b64decode(resp.text)))
        if result.get("code") not in (0, None):
            raise CloudError(f"API error {result.get('code')}: {result.get('message')}")
        return result.get("data") or {}

    def camera_fetch(self, url: str, payload: dict | None = None, _retry=True) -> bytes:
        """Raw GET for camera media: a signed service URL when payload is given, else a pre-signed one."""
        if not self.logged_in:
            raise CloudError("not logged in")
        params = None
        if payload is not None:
            params, _ = self._rc4_params(urlparse(url).path, payload, "GET")
            params["yetAnotherServiceToken"] = self.data["service_token"]
        resp = self._http.get(url, params=params, cookies=self._cookies, timeout=30)
        if resp.status_code in (401, 403) and _retry:
            self.renew()
            return self.camera_fetch(url, payload, _retry=False)
        if resp.status_code != 200 or int(resp.headers.get("x-xiaomi-status-code", 200)) >= 400:
            raise CloudError(f"HTTP {resp.status_code}")
        return resp.content

    def fetch_homes(self) -> list[dict]:
        """Every home with its rooms and devices: [{id, name, rooms: [{name, dids}], devices: [...]}]."""
        homes = []
        result = self.call("/v2/homeroom/gethome", {"fg": True, "fetch_share": True, "fetch_share_dev": True,
                                                     "limit": 300, "app_ver": 7})
        for home in result.get("homelist") or []:
            devices = self.call("/v2/home/home_device_list", {
                "home_owner": int(self.data["user_id"]), "home_id": int(home["id"]), "limit": 300,
                "get_split_device": True, "support_smart_home": True,
            }).get("device_info") or []
            homes.append({
                "id": str(home["id"]),
                "name": home.get("name", ""),
                "rooms": [{"name": r["name"], "dids": [str(d) for d in r.get("dids", [])]}
                          for r in home.get("roomlist") or []],
                "devices": devices,
            })
        return homes
