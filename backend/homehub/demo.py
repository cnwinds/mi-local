"""Demo mode (HUB_DEMO=1): a made-up three-bedroom flat with simulated devices, to try the app without any.

seed() writes the demo home into an empty data directory; DemoDriver keeps each device's state in memory and
answers the same commands as the real drivers.
"""
import json

from .store import DATA_DIR, devices_file, floorplan_file, settings_file

ROOMS = {
    "主卧": [[0, 0], [300, 0], [300, 240], [0, 240]],
    "卫生间": [[310, 0], [450, 0], [450, 150], [310, 150]],
    "次卧": [[460, 0], [720, 0], [720, 240], [460, 240]],
    "书房": [[730, 0], [930, 0], [930, 240], [730, 240]],
    "走廊": [[310, 160], [450, 160], [450, 250], [930, 250], [930, 300], [0, 300], [0, 250], [310, 250]],
    "厨房": [[0, 310], [230, 310], [230, 470], [0, 470]],
    "餐厅": [[0, 480], [230, 480], [230, 620], [0, 620]],
    "客厅": [[240, 310], [760, 310], [760, 620], [240, 620]],
    "阳台": [[770, 310], [930, 310], [930, 620], [770, 620]],
}
# The hallway's bounding box starts in the bedroom's corner; put its name in the hallway itself.
LABELS = {"走廊": [12, 262]}
AC_CAPS = {"modes": ["cool", "heat", "dry", "fan", "auto"], "temp_min": 16, "temp_max": 30, "temp_step": 1,
           "fan_levels": 3}
# (id, name, room, kind, model, spot on the plan, initial state)
DEVICES = [
    ("demo-l1", "吸顶灯", "客厅", "light", "demo.light.ceiling", (500, 470), {"power": True, "brightness": 80, "color_temp": 40}),
    ("demo-l2", "筒灯", "客厅", "light", "demo.light.downlight", (330, 390), {"power": True, "brightness": 45, "color_temp": 30}),
    ("demo-l3", "筒灯 2", "客厅", "light", "demo.light.downlight", (670, 390), {"power": True, "brightness": 45, "color_temp": 30}),
    ("demo-a1", "客厅空调", "客厅", "ac", "demo.aircondition", (500, 340),
     {"power": True, "mode": "cool", "target_temp": 26, "temperature": 27.5, "fan_level": 0, "swing": False, "caps": AC_CAPS}),
    ("demo-c1", "客厅窗帘", "客厅", "curtain", "demo.curtain", (740, 470), {"position": 70}),
    ("demo-p1", "电视插座", "客厅", "plug", "demo.plug", (330, 580), {"power": True, "load_power": 86.5}),
    ("demo-l4", "餐厅吊灯", "餐厅", "light", "demo.light.pendant", (115, 550), {"power": True, "brightness": 100, "color_temp": 20}),
    ("demo-l5", "厨房灯", "厨房", "light", "demo.light.ceiling", (115, 380), {"power": False, "brightness": 100, "color_temp": 70}),
    ("demo-o1", "油烟机", "厨房", "other", "demo.hood", (50, 440), {"power": False}),
    ("demo-l6", "主卧灯", "主卧", "light", "demo.light.ceiling", (150, 130), {"power": False, "brightness": 60, "color_temp": 30}),
    ("demo-a2", "主卧空调", "主卧", "ac", "demo.aircondition", (150, 30),
     {"power": False, "mode": "cool", "target_temp": 25, "temperature": 26.0, "fan_level": 0, "swing": False, "caps": AC_CAPS}),
    ("demo-c2", "主卧窗帘", "主卧", "curtain", "demo.curtain", (30, 130), {"position": 0}),
    ("demo-l7", "次卧灯", "次卧", "light", "demo.light.ceiling", (590, 130), {"power": False, "brightness": 70, "color_temp": 50}),
    ("demo-a3", "次卧空调", "次卧", "ac", "demo.aircondition", (590, 30),
     {"power": True, "mode": "heat", "target_temp": 24, "temperature": 21.5, "fan_level": 2, "swing": False, "caps": AC_CAPS}),
    ("demo-l8", "台灯", "书房", "light", "demo.light.lamp", (830, 120), {"power": True, "brightness": 60, "color_temp": 60}),
    ("demo-b1", "浴霸", "卫生间", "bath_heater", "demo.bathheater", (380, 75),
     {"power": False, "light": False, "heating": False, "blow": False, "ventilation": False, "temperature": 22.0}),
    ("demo-l9", "走廊筒灯", "走廊", "light", "demo.light.downlight", (380, 275), {"power": False, "brightness": 50, "color_temp": 40}),
    ("demo-l10", "玄关筒灯", "走廊", "light", "demo.light.downlight", (700, 275), {"power": False, "brightness": 50, "color_temp": 40}),
    ("demo-r1", "晾衣架", "阳台", "airer", "demo.airer", (850, 440), {"power": False, "light": False, "motor": "stop"}),
    ("demo-o2", "洗衣机", "阳台", "other", "demo.washer", (850, 560), {"power": True}),
]


def seed() -> None:
    """Write the demo home, unless the data directory already holds devices."""
    if (DATA_DIR / "devices.json").exists():
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    devices_file.save([{"id": i, "name": n, "room": r, "kind": k, "model": m, "hidden": False, "driver": "demo",
                        "demo": s} for i, n, r, k, m, _, s in DEVICES])
    settings = settings_file.load()
    settings["rooms"] = list(ROOMS)
    settings_file.save(settings)
    floorplan_file.save({
        "view": [-20, -20, 970, 660],
        "rooms": [{"name": n, "points": p, "label": LABELS.get(n), "outdoor": False} for n, p in ROOMS.items()],
        "devices": {i: list(pos) for i, _, _, _, _, pos, _ in DEVICES},
        "cameras": {},
    })


class DemoDriver:
    poll_interval = 30.0
    offline_retry = 30.0

    def __init__(self, record: dict):
        self.record = record
        self.kind = record["kind"]
        self.state = json.loads(json.dumps(record.get("demo") or {}))

    async def poll(self) -> dict:
        return dict(self.state)

    async def command(self, action: str, value=None) -> None:
        s = self.state
        if action == "toggle":
            action = "turn_off" if s.get("power") else "turn_on"
        if action in ("turn_on", "turn_off"):
            on = action == "turn_on"
            s["power"] = on
            if self.kind == "bath_heater":
                s.update(light=on, heating=False, blow=False, ventilation=False)
            if self.kind == "airer":
                s["light"] = on
        elif action == "set_brightness":
            s.update(power=True, brightness=max(1, min(100, int(value))))
        elif action == "set_color_temp":
            s.update(power=True, color_temp=max(0, min(100, int(value))))
        elif action == "set_temp":
            s["target_temp"] = float(value)
        elif action == "set_mode":
            s["mode"] = value
        elif action == "set_fan":
            s["fan_level"] = int(value)
        elif action == "set_swing":
            s["swing"] = bool(value)
        elif action in ("open", "close"):
            s["position"] = 100 if action == "open" else 0
        elif action == "set_position":
            s["position"] = max(0, min(100, int(value)))
        elif action == "stop":
            s["motor"] = "stop"
        elif action in ("up", "down"):
            s["motor"] = action
        elif action in ("set_light", "set_heating", "set_blow", "set_ventilation"):
            s[action.removeprefix("set_")] = bool(value)
            if self.kind == "bath_heater":
                s["power"] = any(s.get(f) for f in ("light", "heating", "blow", "ventilation"))
            if self.kind == "airer":
                s["power"] = s["light"]
        else:
            raise ValueError(f"unsupported action {action}")
