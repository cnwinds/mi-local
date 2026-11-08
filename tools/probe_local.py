"""Read-only local check: query miIO info from every Wi-Fi device using its token."""
import json
from concurrent.futures import ThreadPoolExecutor

from miio import Device


def load_devices(path="tokens.json"):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for server in data:
        for home in server["homes"]:
            yield from home["devices"]


def probe(dev):
    ip, token = dev.get("localip"), dev.get("token")
    try:
        info = Device(ip, token, timeout=3).info()
        return dev, f"OK  fw={info.firmware_version}"
    except Exception as e:
        return dev, f"ERR {type(e).__name__}"


if __name__ == "__main__":
    devices = list(load_devices())
    wifi = [d for d in devices if d.get("token") and str(d.get("localip", "")).startswith("192.168.1.")]
    with ThreadPoolExecutor(16) as pool:
        results = list(pool.map(probe, wifi))
    for dev, status in sorted(results, key=lambda r: r[1]):
        print(f"{status:28} {dev['localip']:15} {dev['model']:28} {dev['name']}")
    print(f"\n{sum(s.startswith('OK') for _, s in results)}/{len(results)} reachable locally")

    print("\nparent of sub-devices:")
    for d in devices:
        if d.get("parent_id"):
            print(f"  {d['model']:24} {d['name']:12} parent={d['parent_id']} {d.get('parent_model', '')}")
