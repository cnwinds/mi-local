import json
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("HUB_DATA", Path(__file__).resolve().parents[2] / "data"))


class JsonFile:
    def __init__(self, name: str, default):
        self.path = DATA_DIR / name
        self.default = default

    def load(self):
        if not self.path.exists():
            return json.loads(json.dumps(self.default))
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def save(self, data) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)


devices_file = JsonFile("devices.json", [])
rules_file = JsonFile("rules.json", [])
settings_file = JsonFile("settings.json", {"lan_ip": "0.0.0.0", "rooms": []})
cloud_file = JsonFile("cloud.json", {})
