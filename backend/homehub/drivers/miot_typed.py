"""Standard MIoT services mapped onto the hub's typed device state.

Any light, air conditioner, curtain or outlet with a spec gets the same state and commands as the hand-written
drivers, so it shows up with the matching tile. Properties are found by their urn names, not by siid/piid, which
differ from model to model.
"""

# Spec device types with a dedicated tile; everything else stays "other" with the generic property panel.
KIND_BY_TYPE = {"light": "light", "air-conditioner": "ac", "curtain": "curtain", "outlet": "plug"}

AC_MODES = (("cool", "cool"), ("heat", "heat"), ("dry", "dry"), ("dehumid", "dry"), ("fan", "fan"), ("wind", "fan"),
            ("auto", "auto"))


def _scale(value, lo, hi, to_lo, to_hi):
    if hi == lo:
        return to_lo
    return to_lo + (float(value) - lo) * (to_hi - to_lo) / (hi - lo)


def _named(field: dict | None, *words: str):
    """The value whose English name contains one of the words, e.g. the "Open" of a curtain's motor control."""
    for v in (field or {}).get("values", []):
        name = str(v.get("name", "")).lower()
        if any(w in name for w in words):
            return v["value"]
    return None


class TypedMapping:
    def __init__(self, kind: str, fields: list[dict]):
        self.kind = kind
        self._by: dict[tuple[str, str], dict] = {}
        for f in fields:
            if f.get("siid") is not None:
                self._by.setdefault((f.get("svc", ""), f["prop"]), f)
        pick = self._pick
        self.temperature = pick(("environment", "temperature"), ("temperature-humidity-sensor", "temperature"))
        self.on = None
        if kind == "light":
            self.on = pick(("light", "on"))
            self.brightness = pick(("light", "brightness"))
            self.color_temp = pick(("light", "color-temperature"))
        elif kind == "ac":
            self.on = pick(("air-conditioner", "on"))
            self.mode = pick(("air-conditioner", "mode"))
            self.target = pick(("air-conditioner", "target-temperature"))
            self.fan = pick(("fan-control", "fan-level"), ("air-conditioner", "fan-level"))
            self.swing = pick(("fan-control", "vertical-swing"), ("fan-control", "horizontal-swing"))
            self.temperature = self.temperature or pick(("air-conditioner", "temperature"))
            self.modes = {}
            for v in (self.mode or {}).get("values", []):
                name = str(v.get("name", "")).lower()
                mode = next((m for word, m in AC_MODES if word in name), None)
                if mode and mode not in self.modes.values():
                    self.modes[v["value"]] = mode
            self.fan_auto = _named(self.fan, "auto")
            self.fan_levels = sorted(v["value"] for v in (self.fan or {}).get("values", []) if v["value"] != self.fan_auto)
        elif kind == "curtain":
            self.motor = pick(("curtain", "motor-control"))
            self.position = pick(("curtain", "current-position"), ("curtain", "target-position"))
            self.target = pick(("curtain", "target-position"))
        elif kind == "plug":
            self.on = pick(("switch", "on"))
            self.load = pick(("power-consumption", "electric-power"), ("switch", "electric-power"))

    def _pick(self, *keys: tuple[str, str]) -> dict | None:
        return next((self._by[k] for k in keys if k in self._by), None)

    @staticmethod
    def _value(props: dict, field: dict | None):
        return props.get(field["key"]) if field else None

    def caps(self) -> dict:
        lo, hi, step = (self.target or {}).get("range") or (16, 31, 1)
        levels = len(self.fan_levels) or (int(self.fan["range"][1] - self.fan["range"][0]) + 1
                                          if self.fan and self.fan.get("range") else 0)
        return {"modes": list(self.modes.values()) or ["auto"], "temp_min": lo, "temp_max": hi, "temp_step": step,
                "fan_levels": levels}

    def state(self, props: dict) -> dict:
        v = lambda f: self._value(props, f)  # noqa: E731
        state: dict = {}
        if v(self.temperature) is not None:
            state["temperature"] = round(float(v(self.temperature)), 1)
        if self.on and v(self.on) is not None:
            state["power"] = bool(v(self.on))
        if self.kind == "light":
            if self.brightness and v(self.brightness) is not None:
                lo, hi, _ = self.brightness.get("range") or (1, 100, 1)
                state["brightness"] = max(1, min(100, round(_scale(v(self.brightness), lo, hi, 1, 100))))
            if self.color_temp and v(self.color_temp) is not None and self.color_temp.get("range"):
                lo, hi, _ = self.color_temp["range"]
                state["color_temp"] = max(0, min(100, round(_scale(v(self.color_temp), lo, hi, 0, 100))))
        elif self.kind == "ac":
            state["caps"] = self.caps()
            if v(self.mode) is not None:
                state["mode"] = self.modes.get(v(self.mode), "auto")
            if v(self.target) is not None:
                state["target_temp"] = float(v(self.target))
            fan = v(self.fan)
            if fan is not None:
                # 0 is auto; levels count from 1, whatever codes the model uses.
                if self.fan_levels:
                    state["fan_level"] = self.fan_levels.index(fan) + 1 if fan in self.fan_levels else 0
                elif self.fan.get("range"):
                    state["fan_level"] = int(fan - self.fan["range"][0] + 1)
            if v(self.swing) is not None:
                state["swing"] = bool(v(self.swing))
        elif self.kind == "curtain":
            if v(self.position) is not None:
                state["position"] = max(0, min(100, int(v(self.position))))
        elif self.kind == "plug":
            if v(self.load) is not None:
                state["load_power"] = round(float(v(self.load)), 1)
        return state

    def writes(self, action: str, value, props: dict) -> dict[str, object] | None:
        """Property writes {key: value} for a typed command, or None if this mapping doesn't handle it."""
        if action == "toggle" and self.on:
            action = "turn_off" if props.get(self.on["key"]) else "turn_on"
        if action in ("turn_on", "turn_off") and self.on:
            return {self.on["key"]: action == "turn_on"}
        if self.kind == "light":
            if action == "set_brightness" and self.brightness:
                lo, hi, _ = self.brightness.get("range") or (1, 100, 1)
                return {**self._power_on(), self.brightness["key"]: _scale(max(1, min(100, value)), 1, 100, lo, hi)}
            if action == "set_color_temp" and self.color_temp and self.color_temp.get("range"):
                lo, hi, _ = self.color_temp["range"]
                return {**self._power_on(), self.color_temp["key"]: _scale(max(0, min(100, value)), 0, 100, lo, hi)}
        elif self.kind == "ac":
            if action == "set_temp" and self.target:
                return {self.target["key"]: float(value)}
            if action == "set_mode" and self.mode:
                code = next((c for c, m in self.modes.items() if m == value), None)
                if code is None:
                    raise ValueError(f"unsupported mode {value}")
                return {self.mode["key"]: code}
            if action == "set_fan" and self.fan:
                level = int(value)
                if self.fan_levels:
                    if level <= 0 and self.fan_auto is not None:
                        return {self.fan["key"]: self.fan_auto}
                    return {self.fan["key"]: self.fan_levels[max(0, min(len(self.fan_levels), level) - 1)]}
                lo = self.fan["range"][0] if self.fan.get("range") else 0
                return {self.fan["key"]: lo + max(1, level) - 1}
            if action == "set_swing" and self.swing:
                return {self.swing["key"]: bool(value)}
        elif self.kind == "curtain":
            words = {"open": ("open",), "close": ("close",), "stop": ("pause", "stop")}.get(action)
            if words and self.motor and _named(self.motor, *words) is not None:
                return {self.motor["key"]: _named(self.motor, *words)}
            if action in ("open", "close") and self.target:
                return {self.target["key"]: 100 if action == "open" else 0}
            if action == "set_position" and self.target:
                return {self.target["key"]: max(0, min(100, int(value)))}
        return None

    def _power_on(self) -> dict:
        return {self.on["key"]: True} if self.on else {}
