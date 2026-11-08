"""Devices that refuse LAN control (or sit on an unreachable subnet), driven through the Mi Home cloud.

MIoT devices use /miotspec/prop/get|set; older ones use /home/rpc/<did> with their legacy miIO methods.
"""
import asyncio
import time

from ..micloud import MiCloud

# One request at a time: the cloud client shares a requests.Session.
_cloud_lock = asyncio.Lock()


async def _call(cloud: MiCloud, path: str, payload: dict):
    async with _cloud_lock:
        return await asyncio.to_thread(cloud.call, path, payload)


class CloudDriver:
    kind = "other"
    fields: list[dict] = []
    poll_interval = 30.0
    offline_retry = 60.0

    def __init__(self, record: dict, cloud: MiCloud):
        self.record = record
        self.cloud = cloud
        self.did = record["id"]


class MiotCloudDriver(CloudDriver):
    PROPS: dict[str, tuple[int, int]] = {}

    async def get_props(self) -> dict:
        names = list(self.PROPS)
        result = await _call(self.cloud, "/miotspec/prop/get", {"params": [
            {"did": self.did, "siid": s, "piid": p} for s, p in self.PROPS.values()]})
        values = {name: r.get("value") for name, r in zip(names, result) if r.get("code") == 0}
        if not values:
            raise RuntimeError(f"cloud read failed: {[r.get('code') for r in result]}")
        return values

    async def set_props(self, **values) -> None:
        result = await _call(self.cloud, "/miotspec/prop/set", {"params": [
            {"did": self.did, "siid": self.PROPS[k][0], "piid": self.PROPS[k][1], "value": v} for k, v in values.items()]})
        failed = [r for r in result if r.get("code") not in (0, 1)]
        if failed:
            raise RuntimeError(f"cloud write failed: {[r.get('code') for r in failed]}")


class AirConditionerDriver(MiotCloudDriver):
    """State: power, mode (cool/heat/dry/fan/auto), target_temp, fan_level (0 = auto), swing, temperature."""

    kind = "ac"
    PROPS = {"power": (2, 1), "mode": (2, 2), "target_temp": (2, 3), "fan_level": (3, 1), "swing": (3, 2)}
    MODES: dict[int, str] = {}
    TEMP_RANGE = (16.0, 31.0, 1.0)
    FAN_LEVELS = 3

    def caps(self) -> dict:
        lo, hi, step = self.TEMP_RANGE
        return {"modes": list(self.MODES.values()), "temp_min": lo, "temp_max": hi, "temp_step": step,
                "fan_levels": self.FAN_LEVELS}

    async def poll(self) -> dict:
        v = await self.get_props()
        state = {
            "power": bool(v.get("power")),
            "mode": self.MODES.get(int(v.get("mode") or 0), "auto"),
            "target_temp": float(v.get("target_temp") or 0),
            "fan_level": int(v.get("fan_level") or 0),
            "swing": bool(v.get("swing")),
            "caps": self.caps(),
        }
        if v.get("temperature") is not None:
            state["temperature"] = float(v["temperature"])
        return state

    async def command(self, action: str, value=None) -> None:
        if action == "toggle":
            action = "turn_off" if (await self.poll())["power"] else "turn_on"
        if action in ("turn_on", "turn_off"):
            await self.set_props(power=action == "turn_on")
        elif action == "set_temp":
            lo, hi, step = self.TEMP_RANGE
            temp = min(hi, max(lo, round(float(value) / step) * step))
            await self.set_props(target_temp=temp if step < 1 else int(temp))
        elif action == "set_mode":
            code = next((c for c, name in self.MODES.items() if name == value), None)
            if code is None:
                raise ValueError(f"unsupported mode {value}")
            await self.set_props(mode=code)
        elif action == "set_fan":
            await self.set_props(fan_level=max(0, min(self.FAN_LEVELS, int(value))))
        elif action == "set_swing":
            await self.set_props(swing=bool(value))
        else:
            raise ValueError(f"unsupported action {action} for air conditioner")


class XiaomiAcC1(AirConditionerDriver):
    """xiaomi.aircondition.ma2 (米家互联网空调 C1)."""

    PROPS = {**AirConditionerDriver.PROPS, "temperature": (4, 1)}
    MODES = {2: "cool", 3: "dry", 4: "fan", 5: "heat"}
    TEMP_RANGE = (16.0, 31.0, 0.5)
    FAN_LEVELS = 7


class AcPartnerV2(AirConditionerDriver):
    """lumi.acpartner.v2 (空调伴侣): drives the AC by infrared, so state is what it last sent."""

    MODES = {0: "auto", 1: "cool", 2: "dry", 3: "heat", 4: "fan"}
    TEMP_RANGE = (17.0, 30.0, 1.0)
    FAN_LEVELS = 3


class BathHeaterDriver(MiotCloudDriver):
    """viomi.bhf_light.v1. "power" is any function running, so a switch toggle turns everything off."""

    kind = "bath_heater"
    PROPS = {"light": (2, 1), "target_temp": (3, 2), "temperature": (3, 3), "heating": (3, 4),
             "blow": (3, 5), "ventilation": (3, 6)}
    FUNCTIONS = ("light", "heating", "blow", "ventilation")

    async def poll(self) -> dict:
        v = await self.get_props()
        state = {f: bool(v.get(f)) for f in self.FUNCTIONS}
        state["power"] = any(state.values())
        for key in ("target_temp", "temperature"):
            if v.get(key) not in (None, ""):
                state[key] = float(v[key])
        return state

    async def command(self, action: str, value=None) -> None:
        if action == "toggle":
            action = "turn_off" if (await self.poll())["power"] else "turn_on"
        if action == "turn_on":
            await self.set_props(light=True)
        elif action == "turn_off":
            await self.set_props(**{f: False for f in self.FUNCTIONS})
        elif action in ("set_light", "set_heating", "set_blow", "set_ventilation"):
            await self.set_props(**{action.removeprefix("set_"): bool(value)})
        elif action == "set_temp":
            await self.set_props(target_temp=int(min(35, max(25, float(value)))))
        else:
            raise ValueError(f"unsupported action {action} for bath heater")


class AirerDriver(CloudDriver):
    """mrbond.airer.m1pro over its legacy miIO methods. motor: 0 stopped, 1 up, 2 down."""

    kind = "airer"
    MOTOR = {"up": 1, "down": 2, "stop": 0}

    async def rpc(self, method: str, params: list):
        return await _call(self.cloud, f"/home/rpc/{self.did}", {"method": method, "params": params})

    async def poll(self) -> dict:
        dry, led, motor, drytime, location = await self.rpc("get_prop", ["dry", "led", "motor", "drytime", "airer_location"])
        return {
            "light": led == "1",
            "power": led == "1",
            "dry": dry not in ("0", 0, None),
            "motor": {1: "up", 2: "down"}.get(int(motor or 0), "stop"),
            "location": int(location or 0),
        }

    async def command(self, action: str, value=None) -> None:
        if action in self.MOTOR:
            await self.rpc("set_motor", [self.MOTOR[action]])
        elif action in ("turn_on", "turn_off", "toggle", "set_light"):
            on = {"turn_on": True, "turn_off": False}.get(action, bool(value))
            if action == "toggle":
                on = not (await self.poll())["light"]
            await self.rpc("set_led", [1 if on else 0])
        else:
            raise ValueError(f"unsupported action {action} for airer")


INT_FORMATS = ("int8", "uint8", "int16", "uint16", "int32", "uint32", "int64", "uint64")

# Legacy miIO properties some models report beyond their MIoT spec: (prop, label, format, unit, values).
LEGACY_EXTRAS: dict[str, list[tuple]] = {
    "viomi.hood.c1": [
        ("link_state", "烟灶联动", "bool", None, []),
        ("poweroff_delaytime", "延时关机", "uint16", "seconds", []),
    ],
    "viomi.waterheater.u1": [
        ("errStatus", "故障", "uint8", None, [{"value": 0, "label": "无故障"}]),
    ],
}


def legacy_fields(model: str) -> list[dict]:
    return [{"key": f"x.{prop}", "siid": None, "piid": None, "service": "其他", "name": label, "prop": prop,
             "format": fmt, "unit": unit, "range": None, "values": values, "writable": False, "vendor": False}
            for prop, label, fmt, unit, values in LEGACY_EXTRAS.get(model, [])]


class MiotGenericDriver(CloudDriver):
    """Any device with a MIoT spec: reads every readable property through the cloud.

    State: {"props": {"siid.piid": value}, "power": main switch if the device has one}.
    """

    poll_interval = 60.0
    offline_retry = 120.0
    WRITE_SETTLE = 10.0

    def __init__(self, record: dict, cloud: MiCloud, fields: list[dict]):
        super().__init__(record, cloud)
        self._written: dict[str, tuple] = {}
        self.kind = record.get("kind", "other")
        self.fields = fields + legacy_fields(record.get("model", ""))
        self.by_key = {f["key"]: f for f in self.fields}
        main = min((f["siid"] for f in fields), default=None)
        self.power_key = next((f["key"] for f in fields if f["siid"] == main and f["prop"] == "on"), None)

    async def poll(self) -> dict:
        spec = [f for f in self.fields if f["siid"] is not None]
        result = await _call(self.cloud, "/miotspec/prop/get", {"params": [
            {"did": self.did, "siid": f["siid"], "piid": f["piid"]} for f in spec]})
        props = {f"{r['siid']}.{r['piid']}": r.get("value") for r in result if r.get("code") == 0}
        if not props:
            raise RuntimeError(f"cloud read failed: {sorted({r.get('code') for r in result})}")
        # The cloud keeps answering with the old value for a few seconds after a write.
        now = time.monotonic()
        self._written = {k: (v, t) for k, (v, t) in self._written.items() if now - t < self.WRITE_SETTLE}
        props.update({k: v for k, (v, _) in self._written.items() if k in props})
        legacy = [f["prop"] for f in self.fields if f["siid"] is None]
        if legacy:
            try:
                values = await _call(self.cloud, f"/home/rpc/{self.did}", {"method": "get_prop", "params": legacy})
                props.update({f"x.{p}": v for p, v in zip(legacy, values) if v not in ("error", None)})
            except Exception:
                pass
        state = {"props": props}
        if self.power_key and self.power_key in props:
            state["power"] = bool(props[self.power_key])
        return state

    async def set_prop(self, key: str, value) -> None:
        field = self.by_key.get(key)
        if not field or not field["writable"]:
            raise ValueError(f"property {key} is not writable")
        if field["format"] == "bool":
            value = bool(value)
        elif field["format"] in INT_FORMATS or field["format"] == "float":
            value = float(value)
            if field["range"]:
                lo, hi, step = field["range"]
                value = min(hi, max(lo, lo + round((value - lo) / step) * step))
            if field["format"] in INT_FORMATS:
                value = int(value)
        if field["values"] and value not in [v["value"] for v in field["values"]]:
            raise ValueError(f"invalid value {value!r} for {key}")
        result = await _call(self.cloud, "/miotspec/prop/set", {"params": [
            {"did": self.did, "siid": field["siid"], "piid": field["piid"], "value": value}]})
        if any(r.get("code") not in (0, 1) for r in result):
            raise RuntimeError(f"cloud write failed: {[r.get('code') for r in result]}")
        self._written[key] = (value, time.monotonic())

    async def command(self, action: str, value=None) -> None:
        if action == "set_prop":
            await self.set_prop(value["key"], value["value"])
            return
        if action in ("turn_on", "turn_off", "toggle") and self.power_key:
            on = action == "turn_on" if action != "toggle" else not (await self.poll()).get("power")
            await self.set_prop(self.power_key, on)
            return
        raise ValueError(f"unsupported action {action}")


CLOUD_DRIVERS = {
    "xiaomi.aircondition.ma2": XiaomiAcC1,
    "lumi.acpartner.v2": AcPartnerV2,
    "viomi.bhf_light.v1": BathHeaterDriver,
    "mrbond.airer.m1pro": AirerDriver,
}
