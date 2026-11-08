"""Xiaomi Gateway 2 (lumi.gateway.v3) LAN protocol, proto_version 1.x.

Events arrive as multicast on 224.0.0.50:9898. read/write go unicast to gateway:9898
from a separate ephemeral socket: the gateway does not answer requests sent from port 9898.
"""
import asyncio
import json
import logging
import socket
import struct
import time
from typing import Callable

from Crypto.Cipher import AES

log = logging.getLogger(__name__)

MCAST = "224.0.0.50"
PORT = 9898
IV = bytes.fromhex("17996d093d28ddb3ba695a2e6f58562e")

KIND_BY_MODEL = {"switch": "switch", "plug": "plug", "curtain": "curtain"}
SWITCH_EVENTS = {"click", "double_click", "long_click_press", "long_click_release"}


def norm_sid(sid: str) -> str:
    return sid.lstrip("0")


def parse_state(model: str, data: dict) -> dict:
    state = {}
    if model == "switch" and "voltage" in data:
        state["battery"] = max(0, min(100, round((int(data["voltage"]) - 2800) / 4)))
    if model == "plug":
        if data.get("status") in ("on", "off"):
            state["power"] = data["status"] == "on"
        if "load_power" in data:
            state["load_power"] = float(data["load_power"])
    elif model == "curtain":
        if "curtain_level" in data:
            state["position"] = int(data["curtain_level"])
    return state


class _Protocol(asyncio.DatagramProtocol):
    def __init__(self, handler):
        self.handler = handler

    def datagram_received(self, data, addr):
        try:
            self.handler(json.loads(data), addr)
        except Exception:
            log.exception("bad datagram from %s: %r", addr, data)


class Gateway2:
    def __init__(self, ip: str, sid: str, lan_key: str, lan_ip: str,
                 on_state: Callable[[str, str, dict], None],
                 on_event: Callable[[str, str, str], None]):
        self.ip = ip
        self.sid = norm_sid(sid)
        self.lan_key = lan_key
        self.lan_ip = lan_ip
        self.on_state = on_state
        self.on_event = on_event
        self.models: dict[str, str] = {}
        self.short_ids: dict[str, int] = {}
        self._token: str | None = None
        self._token_ready = asyncio.Event()
        self._pending: dict[tuple[str, str], asyncio.Future] = {}
        self._transport = None
        self._mcast_transport = None
        self._request_lock: asyncio.Lock | None = None
        self.last_seen = 0.0

    async def start(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", PORT))
        mreq = struct.pack("4s4s", socket.inet_aton(MCAST), socket.inet_aton(self.lan_ip))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.setblocking(False)
        self._request_lock = asyncio.Lock()
        loop = asyncio.get_running_loop()
        self._mcast_transport, _ = await loop.create_datagram_endpoint(lambda: _Protocol(self._handle), sock=sock)
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: _Protocol(self._handle), local_addr=("0.0.0.0", 0))

    def stop(self) -> None:
        for transport in (self._mcast_transport, self._transport):
            if transport:
                transport.close()
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()

    @property
    def connected(self) -> bool:
        # The gateway multicasts a heartbeat every 10 s.
        return time.time() - self.last_seen < 35

    def _handle(self, msg: dict, addr) -> None:
        if addr[0] != self.ip:
            return
        self.last_seen = time.time()
        cmd = msg.get("cmd", "")
        sid = norm_sid(msg.get("sid", ""))
        data = json.loads(msg.get("data") or "{}")
        if cmd.endswith("_ack"):
            fut = self._pending.pop((cmd, sid), None)
            if fut and not fut.done():
                fut.set_result(data)
        if sid == self.sid:
            if cmd == "heartbeat" and msg.get("token"):
                self._token = msg["token"]
                self._token_ready.set()
            return
        model = msg.get("model", "")
        self.models[sid] = model
        if "short_id" in msg:
            self.short_ids[sid] = msg["short_id"]
        if cmd in ("heartbeat", "report", "read_ack", "write_ack") and "error" not in data:
            self.on_state(sid, model, {"online": True, **parse_state(model, data)})
        if cmd == "report" and model == "switch" and data.get("status") in SWITCH_EVENTS:
            self.on_event(sid, model, data["status"])

    async def _request(self, cmd: str, sid: str, payload: dict, timeout=3.0, attempts=2) -> dict:
        # The gateway drops requests that arrive in bursts, so send one at a time.
        key = (f"{cmd}_ack", norm_sid(sid))
        async with self._request_lock:
            for attempt in range(attempts):
                fut = asyncio.get_running_loop().create_future()
                self._pending[key] = fut
                self._transport.sendto(json.dumps(payload).encode(), (self.ip, PORT))
                try:
                    return await asyncio.wait_for(fut, timeout)
                except asyncio.TimeoutError:
                    if attempt == attempts - 1:
                        raise
                finally:
                    self._pending.pop(key, None)

    async def device_ids(self) -> list[str]:
        """Sub-devices in the gateway's own table, including stale ones that never answer."""
        return await self._request("get_id_list", self.sid, {"cmd": "get_id_list"})

    async def read(self, sid: str) -> dict:
        # Sub-devices that left the gateway never answer; a single short try keeps them from hogging the queue.
        return await self._request("read", sid, {"cmd": "read", "sid": sid}, timeout=2.0, attempts=1)

    async def write(self, sid: str, params: dict) -> dict:
        if not self.lan_key:
            raise RuntimeError("还没有设置网关的局域网密钥")
        await asyncio.wait_for(self._token_ready.wait(), 15)
        key = AES.new(self.lan_key.encode(), AES.MODE_CBC, IV).encrypt(self._token.encode()).hex()
        is_gateway = norm_sid(sid) == self.sid
        payload = {
            "cmd": "write",
            "model": "gateway" if is_gateway else self.models.get(norm_sid(sid), ""),
            "sid": sid,
            "short_id": self.short_ids.get(norm_sid(sid), 0),
            "data": json.dumps({**params, "key": key}),
        }
        result = await self._request("write", sid, payload)
        if "error" in result:
            raise RuntimeError(f"gateway write failed: {result['error']}")
        return result


class Gw2DeviceDriver:
    """Adapter so gateway sub-devices look like other drivers to the hub."""

    poll_interval = 300.0
    offline_retry = 300.0

    def __init__(self, record: dict, gateway: Gateway2):
        self.record = record
        self.kind = record["kind"]
        self.sid = record["sid"]
        self.gateway = gateway

    async def poll(self) -> dict:
        data = await self.gateway.read(self.sid)
        if "error" in data:
            raise RuntimeError(data["error"])
        self.gateway.models.setdefault(norm_sid(self.sid), self.record.get("gw_model", ""))
        return parse_state(self.record.get("gw_model", ""), data)

    async def command(self, action: str, value=None) -> None:
        if self.kind == "plug":
            if action == "toggle":
                state = await self.poll()
                action = "turn_off" if state.get("power") else "turn_on"
            if action in ("turn_on", "turn_off"):
                await self.gateway.write(self.sid, {"status": "on" if action == "turn_on" else "off"})
                return
        elif self.kind == "curtain":
            if action in ("open", "close", "stop"):
                await self.gateway.write(self.sid, {"curtain_status": action})
                return
            if action == "set_position":
                await self.gateway.write(self.sid, {"curtain_level": str(int(value))})
                return
        raise ValueError(f"unsupported action {action} for {self.kind}")


class Gw2DoorbellDriver:
    """The gateway's own speaker. Ringtone ids (mid): 10-13 are doorbell chimes, 10000 stops playback."""

    kind = "doorbell"
    poll_interval = 300.0
    offline_retry = 60.0

    def __init__(self, record: dict, gateway: Gateway2):
        self.record = record
        self.gateway = gateway

    async def poll(self) -> dict:
        await self.gateway.device_ids()
        return {}

    async def command(self, action: str, value=None) -> None:
        if action == "ring":
            mid = int(self.record.get("tone", 10))
            vol = int(value if value is not None else self.record.get("volume", 50))
            await self.gateway.write(self.gateway.sid, {"mid": mid, "vol": vol})
        elif action == "stop":
            await self.gateway.write(self.gateway.sid, {"mid": 10000})
        else:
            raise ValueError(f"unsupported action {action} for doorbell")
