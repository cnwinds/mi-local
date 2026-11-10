"""Where MIoT property reads and writes go: the device itself over miIO, or the Mi Home cloud.

Newer Wi-Fi devices answer get_properties/set_properties on the LAN. Older ones only speak their legacy miIO
methods there, and the cloud translates the spec for them; HybridTransport finds out per device.
"""
import asyncio
import logging
import time

from miio import Device

from ..micloud import MiCloud

log = logging.getLogger(__name__)

# One request at a time: the cloud client shares a requests.Session.
_cloud_lock = asyncio.Lock()


async def cloud_call(cloud: MiCloud, path: str, payload: dict):
    async with _cloud_lock:
        return await asyncio.to_thread(cloud.call, path, payload)


class CloudTransport:
    name = "cloud"

    def __init__(self, cloud: MiCloud, did: str):
        self.cloud = cloud
        self.did = did

    async def get(self, params: list[dict]) -> list[dict]:
        return await cloud_call(self.cloud, "/miotspec/prop/get", {"params": params})

    async def set(self, params: list[dict]) -> list[dict]:
        return await cloud_call(self.cloud, "/miotspec/prop/set", {"params": params})

    async def rpc(self, method: str, params: list):
        return await cloud_call(self.cloud, f"/home/rpc/{self.did}", {"method": method, "params": params})


class LanTransport:
    name = "lan"
    # Long property lists overflow what some devices answer in one UDP packet.
    CHUNK = 15

    def __init__(self, ip: str, token: str):
        self._dev = Device(ip, token, timeout=2)
        self._lock = asyncio.Lock()

    async def _send(self, method: str, params):
        async with self._lock:
            return await asyncio.to_thread(self._dev.send, method, params, 1)

    async def _chunked(self, method: str, params: list[dict]) -> list[dict]:
        out = []
        for i in range(0, len(params), self.CHUNK):
            out += await self._send(method, params[i:i + self.CHUNK])
        return out

    async def get(self, params: list[dict]) -> list[dict]:
        return await self._chunked("get_properties", params)

    async def set(self, params: list[dict]) -> list[dict]:
        return await self._chunked("set_properties", params)

    async def rpc(self, method: str, params: list):
        return await self._send(method, params)


class LanUnsupported(Exception):
    pass


class HybridTransport:
    """LAN first. A device whose LAN side fails or answers no property moves to the cloud, and gets another LAN try
    after LAN_RETRY. Without a cloud session, LAN errors are simply raised."""

    LAN_RETRY = 1800.0

    def __init__(self, lan: LanTransport, cloud: CloudTransport | None, clock=time.monotonic):
        self.lan = lan
        self.cloud = cloud
        self.clock = clock
        self._cloud_until = 0.0

    @property
    def name(self) -> str:
        return "cloud" if self.cloud and self.clock() < self._cloud_until else "lan"

    async def _run(self, op: str, *args):
        if self.name == "cloud":
            return await getattr(self.cloud, op)(*args)
        try:
            result = await getattr(self.lan, op)(*args)
            ok = (0,) if op == "get" else (0, 1)
            if op in ("get", "set") and result and not any(r.get("code") in ok for r in result):
                raise LanUnsupported(sorted({r.get("code") for r in result}))
            return result
        except Exception as e:
            if not self.cloud:
                raise
            log.info("LAN %s failed (%s), using the cloud for %.0f min", op, e, self.LAN_RETRY / 60)
            self._cloud_until = self.clock() + self.LAN_RETRY
            return await getattr(self.cloud, op)(*args)

    async def get(self, params: list[dict]) -> list[dict]:
        return await self._run("get", params)

    async def set(self, params: list[dict]) -> list[dict]:
        return await self._run("set", params)

    async def rpc(self, method: str, params: list):
        return await self._run("rpc", method, params)
