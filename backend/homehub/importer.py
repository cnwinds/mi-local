"""Build data/devices.json from the token extractor export (one-off bootstrap).

Usage: python -m homehub.importer tokens.json secrets.json
Prefer the in-app Mi Home sync, which also fills in rooms.
"""
import json
import sys

from .catalog import merge
from .store import devices_file


def main(tokens_path: str, secrets_path: str) -> None:
    with open(tokens_path, encoding="utf-8") as f:
        devices = [d for s in json.load(f) for h in s["homes"] for d in h["devices"]]
    with open(secrets_path, encoding="utf-8") as f:
        gw = json.load(f)["gateway2"]
    existing = {r["id"]: r for r in devices_file.load()}
    records, summary = merge(devices, {}, existing, str(gw["did"]), gw["lan_key"])
    devices_file.save(records)
    print(f"saved {len(records)} devices to {devices_file.path}; added {len(summary['added'])}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
