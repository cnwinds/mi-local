"""Device pairing: every browser pairs once with a short code, then carries a token cookie; its role decides what it may do.

The hub keeps only SHA-256 hashes of the tokens. Codes live in memory, except the bootstrap code, which sits in a file
so the command line (`python -m homehub.auth`) can mint one for a running hub.
"""

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
import uuid
from pathlib import Path

from .store import DATA_DIR, JsonFile

log = logging.getLogger(__name__)

COOKIE = "hub_token"
COOKIE_MAX_AGE = 10 * 365 * 86400
ROLES = ("admin", "family", "panel")
ROLE_NAMES = {"admin": "管理员", "family": "家人", "panel": "墙面面板"}
PERMISSIONS = {
    "admin": {"view", "control", "cameras", "history", "admin"},
    "family": {"view", "control", "cameras", "history"},
    "panel": {"view", "control"},
}

CODE_TTL = 300
CODE_ATTEMPTS = 5
BOOTSTRAP_TTL = 24 * 3600
BOOTSTRAP_ATTEMPTS = 10
BOOTSTRAP_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
IP_FAILURES = 10
IP_WINDOW = 600
# last_seen is only written back this often, to spare the flash.
SEEN_EVERY = 3600

_VIEW = {"/api/devices", "/api/rooms", "/api/panels", "/api/scenes", "/api/floorplan", "/api/ws"}
_FIELDS = re.compile(r"^/api/devices/[^/]+/fields$")
_COMMAND = re.compile(r"^/api/devices/[^/]+/command$")
_SCENE_RUN = re.compile(r"^/api/scenes/[^/]+/run$")


def required_permission(method: str, path: str) -> str | None:
    """What a request needs; None when anyone may make it. Routes not listed here are admin only."""
    if not path.startswith("/api/"):
        return None
    if path in ("/api/auth/me", "/api/auth/pair", "/api/lockin/ca.crt"):
        return None
    if path.startswith("/api/cameras"):
        return "cameras" if method == "GET" else "admin"
    if method == "GET" and path in ("/api/events", "/api/stats"):
        return "history"
    if method == "GET" and (path in _VIEW or _FIELDS.match(path)):
        return "view"
    if method == "POST" and (_COMMAND.match(path) or _SCENE_RUN.match(path)):
        return "control"
    return "admin"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_code(code: str) -> str:
    return re.sub(r"[^0-9A-Z]", "", code.upper())


class PairError(Exception):
    pass


class TooManyAttempts(Exception):
    pass


def write_bootstrap_code(path: Path, now: float) -> str:
    """A one-time admin code, good for a day; replaces any earlier one."""
    raw = "".join(secrets.choice(BOOTSTRAP_ALPHABET) for _ in range(8))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"hash": token_hash(raw), "expires": now + BOOTSTRAP_TTL, "attempts": 0}))
    os.replace(tmp, path)
    return f"{raw[:4]}-{raw[4:]}"


class Auth:
    def __init__(self, file: JsonFile | None = None, bootstrap_path: Path | None = None, clock=time.time):
        self.file = file or JsonFile("auth.json", {"devices": []})
        self.bootstrap_path = bootstrap_path or DATA_DIR / "pairing-code.json"
        self.clock = clock
        # [{"id", "name", "role", "token": sha256, "created", "last_seen", "ip"}]
        self.devices: list[dict] = self.file.load().get("devices", [])
        # code -> {"role", "expires", "attempts"}
        self.codes: dict[str, dict] = {}
        self.failures: dict[str, list[float]] = {}

    def save(self) -> None:
        self.file.save({"devices": self.devices})

    @property
    def has_admin(self) -> bool:
        return any(d["role"] == "admin" for d in self.devices)

    def ensure_bootstrap(self) -> None:
        """With no admin yet, log a one-time code so the owner can pair the first device from the hub's log."""
        if self.has_admin:
            return
        code = write_bootstrap_code(self.bootstrap_path, self.clock())
        log.warning("还没有管理员设备。在浏览器里打开 mi-local，用这个一次性配对码配对第一台设备（24 小时内有效）：%s", code)

    def authenticate(self, token: str, ip: str = "") -> dict | None:
        if not token:
            return None
        digest = token_hash(token)
        device = next((d for d in self.devices if hmac.compare_digest(d["token"], digest)), None)
        if device:
            now = self.clock()
            if now - device.get("last_seen", 0) > SEEN_EVERY or device.get("ip") != ip:
                device["last_seen"] = now
                device["ip"] = ip
                self.save()
        return device

    def create_code(self, role: str) -> dict:
        if role not in ROLES:
            raise ValueError("没有这个角色")
        now = self.clock()
        self.codes = {c: v for c, v in self.codes.items() if v["expires"] > now}
        code = f"{secrets.randbelow(10**6):06d}"
        while code in self.codes:
            code = f"{secrets.randbelow(10**6):06d}"
        self.codes[code] = {"role": role, "expires": now + CODE_TTL, "attempts": 0}
        return {"code": code, "role": role, "expires_in": CODE_TTL}

    def pair(self, code: str, name: str, ip: str) -> tuple[dict, str]:
        now = self.clock()
        recent = [t for t in self.failures.get(ip, []) if now - t < IP_WINDOW]
        self.failures[ip] = recent
        if len(recent) >= IP_FAILURES:
            raise TooManyAttempts()
        code = normalize_code(code)
        role = self._take_code(code, now) or self._take_bootstrap(code, now)
        if not role:
            self._fail(ip, now)
            raise PairError("配对码不对，或者已经过期")
        token = secrets.token_urlsafe(32)
        device = {
            "id": uuid.uuid4().hex[:8],
            "name": name.strip()[:24] or "未命名设备",
            "role": role,
            "token": token_hash(token),
            "created": now,
            "last_seen": now,
            "ip": ip,
        }
        self.devices.append(device)
        self.save()
        log.info("新设备已配对：%s（%s）", device["name"], ROLE_NAMES[role])
        return device, token

    def _take_code(self, code: str, now: float) -> str | None:
        for c, entry in list(self.codes.items()):
            if entry["expires"] > now and hmac.compare_digest(c, code):
                del self.codes[c]
                return entry["role"]
        return None

    def _read_bootstrap(self) -> dict | None:
        try:
            return json.loads(self.bootstrap_path.read_text())
        except (OSError, ValueError):
            return None

    def _take_bootstrap(self, code: str, now: float) -> str | None:
        data = self._read_bootstrap()
        if not data or data["expires"] <= now or not hmac.compare_digest(data["hash"], token_hash(code)):
            return None
        self.bootstrap_path.unlink(missing_ok=True)
        return "admin"

    def _fail(self, ip: str, now: float) -> None:
        """Every wrong guess counts against all live codes, so none can be brute-forced."""
        self.failures.setdefault(ip, []).append(now)
        for c, entry in list(self.codes.items()):
            entry["attempts"] += 1
            if entry["attempts"] >= CODE_ATTEMPTS or entry["expires"] <= now:
                del self.codes[c]
        data = self._read_bootstrap()
        if data:
            data["attempts"] += 1
            if data["attempts"] >= BOOTSTRAP_ATTEMPTS:
                self.bootstrap_path.unlink(missing_ok=True)
                log.warning("一次性配对码试错太多次，已作废。需要的话执行 python -m homehub.auth 重新生成")
            else:
                self.bootstrap_path.write_text(json.dumps(data))

    def _device(self, device_id: str) -> dict:
        device = next((d for d in self.devices if d["id"] == device_id), None)
        if not device:
            raise KeyError(device_id)
        return device

    def _keeps_an_admin(self, without: dict) -> bool:
        return any(d["role"] == "admin" and d is not without for d in self.devices)

    def update(self, device_id: str, name: str | None = None, role: str | None = None) -> dict:
        device = self._device(device_id)
        if role is not None:
            if role not in ROLES:
                raise ValueError("没有这个角色")
            if device["role"] == "admin" and role != "admin" and not self._keeps_an_admin(device):
                raise ValueError("至少要保留一台管理员设备")
            device["role"] = role
        if name is not None and name.strip():
            device["name"] = name.strip()[:24]
        self.save()
        return device

    def revoke(self, device_id: str) -> None:
        device = self._device(device_id)
        if device["role"] == "admin" and not self._keeps_an_admin(device):
            raise ValueError("至少要保留一台管理员设备")
        self.devices.remove(device)
        self.save()

    @staticmethod
    def public(device: dict, current_id: str | None = None) -> dict:
        return {
            "id": device["id"],
            "name": device["name"],
            "role": device["role"],
            "created": device["created"],
            "last_seen": device.get("last_seen"),
            "ip": device.get("ip", ""),
            "current": device["id"] == current_id,
        }


if __name__ == "__main__":
    # Recovery: run on the hub (docker exec mi-local python -m homehub.auth) to get a fresh one-time admin code.
    print("一次性配对码（24 小时内有效，用一次就作废）：", write_bootstrap_code(DATA_DIR / "pairing-code.json", time.time()))
