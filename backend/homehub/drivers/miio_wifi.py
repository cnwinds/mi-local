"""Wi-Fi devices controlled over the miIO LAN protocol (UDP 54321)."""
import asyncio
import logging

from miio import Device

log = logging.getLogger(__name__)


class MiioDriver:
    kind = "other"
    poll_interval = 60.0

    def __init__(self, record: dict):
        self.record = record
        self._dev = Device(record["ip"], record["token"], timeout=2)
        self._lock = asyncio.Lock()

    async def call(self, method: str, params=None):
        async with self._lock:
            return await asyncio.to_thread(self._dev.send, method, params or [], 1)

    async def poll(self) -> dict:
        await self.call("miIO.info")
        return {}

    async def command(self, action: str, value=None) -> None:
        raise ValueError(f"unsupported action {action}")


class LightDriver(MiioDriver):
    kind = "light"
    poll_interval = 4.0

    async def set_power(self, on: bool) -> None:
        raise NotImplementedError

    async def command(self, action: str, value=None) -> None:
        if action == "turn_on":
            await self.set_power(True)
        elif action == "turn_off":
            await self.set_power(False)
        elif action == "toggle":
            state = await self.poll()
            await self.set_power(not state["power"])
        elif action == "set_brightness":
            await self.set_power(True)
            await self.set_brightness(max(1, min(100, int(value))))
        elif action == "set_color_temp":
            await self.set_power(True)
            await self.set_color_temp(max(0, min(100, int(value))))
        else:
            await super().command(action, value)


class YeelightCeiling(LightDriver):
    """yeelink.light.ceiling*; color_temp is 0 (warm, 2700K) .. 100 (cold, 6500K)."""

    CT_MIN, CT_MAX = 2700, 6500

    async def poll(self) -> dict:
        power, bright, ct = await self.call("get_prop", ["power", "bright", "ct"])
        ct = int(ct or self.CT_MIN)
        return {
            "power": power == "on",
            "brightness": int(bright or 0),
            "color_temp": round((ct - self.CT_MIN) * 100 / (self.CT_MAX - self.CT_MIN)),
        }

    async def set_power(self, on: bool) -> None:
        await self.call("set_power", ["on" if on else "off", "smooth", 300])

    async def set_brightness(self, value: int) -> None:
        await self.call("set_bright", [value, "smooth", 300])

    async def set_color_temp(self, value: int) -> None:
        kelvin = self.CT_MIN + round(value * (self.CT_MAX - self.CT_MIN) / 100)
        await self.call("set_ct_abx", [kelvin, "smooth", 300])


class PhilipsDownlight(LightDriver):
    """philips.light.downlight; native cct is 1..100 (warm..cold)."""

    async def poll(self) -> dict:
        power, bright, cct = await self.call("get_prop", ["power", "bright", "cct"])
        return {"power": power == "on", "brightness": int(bright), "color_temp": int(cct)}

    async def set_power(self, on: bool) -> None:
        await self.call("set_power", ["on" if on else "off"])

    async def set_brightness(self, value: int) -> None:
        await self.call("set_bright", [value])

    async def set_color_temp(self, value: int) -> None:
        await self.call("set_cct", [max(1, value)])


DRIVERS = {
    "yeelight": YeelightCeiling,
    "philips": PhilipsDownlight,
    "miio": MiioDriver,
}
