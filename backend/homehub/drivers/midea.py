"""Midea / Hualing / Little Swan air conditioners over the Midea LAN protocol (TCP 6444, V3 needs a token/key)."""
import asyncio
import logging

from msmart.device import AirConditioner as AC

log = logging.getLogger(__name__)

MODES = {AC.OperationalMode.COOL: "cool", AC.OperationalMode.HEAT: "heat", AC.OperationalMode.DRY: "dry",
         AC.OperationalMode.FAN_ONLY: "fan", AC.OperationalMode.AUTO: "auto"}
FAN_ORDER = (AC.FanSpeed.SILENT, AC.FanSpeed.LOW, AC.FanSpeed.MEDIUM, AC.FanSpeed.HIGH, AC.FanSpeed.MAX)


class MideaAcDriver:
    """Same state shape as the Mi Home AC drivers, so the AC tile works unchanged."""

    kind = "ac"
    poll_interval = 15.0
    offline_retry = 60.0

    def __init__(self, record: dict):
        self.record = record
        self._ac = AC(ip=record["ip"], port=int(record.get("port") or 6444), device_id=int(record["device_id"]))
        self._lock = asyncio.Lock()
        self._ready = False

    async def _connect(self) -> None:
        if self._ready:
            return
        if self.record.get("midea_token"):
            await self._ac.authenticate(self.record["midea_token"], self.record["midea_key"])
        try:
            await self._ac.get_capabilities()
        except Exception as e:
            log.debug("midea %s capabilities unavailable: %s", self.record["id"], e)
        self._ready = True

    async def _refresh(self) -> None:
        try:
            await self._connect()
            await self._ac.refresh()
        except Exception:
            self._ready = False
            raise
        if not self._ac.online:
            self._ready = False
            raise RuntimeError("no response")

    def _fan_levels(self) -> list:
        supported = set(self._ac.supported_fan_speeds or ())
        levels = [s for s in FAN_ORDER if s in supported]
        return levels or [AC.FanSpeed.LOW, AC.FanSpeed.MEDIUM, AC.FanSpeed.HIGH]

    def _modes(self) -> list[str]:
        supported = self._ac.supported_operation_modes or list(MODES)
        return [name for mode, name in MODES.items() if mode in supported]

    def _swing_on(self):
        supported = self._ac.supported_swing_modes or []
        return AC.SwingMode.VERTICAL if not supported or AC.SwingMode.VERTICAL in supported else supported[-1]

    def _state(self) -> dict:
        ac = self._ac
        levels = self._fan_levels()
        speed = ac.fan_speed
        if speed == AC.FanSpeed.AUTO:
            fan_level = 0
        else:
            fan_level = 1 + min(range(len(levels)), key=lambda i: abs(int(levels[i]) - int(speed)))
        state = {
            "power": bool(ac.power_state),
            "mode": MODES.get(ac.operational_mode, "auto"),
            "target_temp": float(ac.target_temperature or 0),
            "fan_level": fan_level,
            "swing": ac.swing_mode != AC.SwingMode.OFF,
            "caps": {"modes": self._modes(), "temp_min": float(ac.min_target_temperature),
                     "temp_max": float(ac.max_target_temperature), "temp_step": 0.5,
                     "fan_levels": len(levels)},
        }
        if ac.indoor_temperature is not None:
            state["temperature"] = float(ac.indoor_temperature)
        return state

    async def poll(self) -> dict:
        async with self._lock:
            await self._refresh()
            return self._state()

    async def command(self, action: str, value=None) -> None:
        async with self._lock:
            await self._refresh()
            ac = self._ac
            if action == "toggle":
                action = "turn_off" if ac.power_state else "turn_on"
            if action in ("turn_on", "turn_off"):
                ac.power_state = action == "turn_on"
            elif action == "set_temp":
                lo, hi = ac.min_target_temperature, ac.max_target_temperature
                ac.target_temperature = min(hi, max(lo, round(float(value) * 2) / 2))
            elif action == "set_mode":
                mode = next((m for m, name in MODES.items() if name == value), None)
                if mode is None:
                    raise ValueError(f"unsupported mode {value}")
                ac.operational_mode = mode
                ac.power_state = True
            elif action == "set_fan":
                levels = self._fan_levels()
                level = max(0, min(len(levels), int(value)))
                ac.fan_speed = AC.FanSpeed.AUTO if level == 0 else levels[level - 1]
            elif action == "set_swing":
                ac.swing_mode = self._swing_on() if value else AC.SwingMode.OFF
            else:
                raise ValueError(f"unsupported action {action} for air conditioner")
            try:
                await ac.apply()
            except Exception:
                self._ready = False
                raise
