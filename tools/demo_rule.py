"""End-to-end local rule demo: Gateway 2 wireless switch click -> toggle a Wi-Fi light.

Usage: python tools/demo_rule.py <local_ip> <light name in Mi Home> [seconds]
"""
import json
import socket
import struct
import sys
import time

from miio import Device

MCAST = "224.0.0.50"
EVENT_PORT = 9898


def find_device(name):
    with open("tokens.json", encoding="utf-8") as f:
        for server in json.load(f):
            for home in server["homes"]:
                for dev in home["devices"]:
                    if dev.get("name") == name:
                        return dev
    raise SystemExit(f"device not found: {name}")


def toggle(light: Device):
    power = light.send("get_prop", ["power"])[0]
    target = "off" if power == "on" else "on"
    light.send("set_power", [target, "sudden", 0])
    return target


def main():
    local_ip, light_name = sys.argv[1], sys.argv[2]
    seconds = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    info = find_device(light_name)
    light = Device(info["localip"], info["token"], timeout=3)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", EVENT_PORT))
    mreq = struct.pack("4s4s", socket.inet_aton(MCAST), socket.inet_aton(local_ip))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.settimeout(1)

    print(f"listening {seconds}s, click any wireless switch on Gateway 2 -> toggle {light_name}", flush=True)
    end = time.time() + seconds
    while time.time() < end:
        try:
            raw, _ = sock.recvfrom(4096)
        except socket.timeout:
            continue
        msg = json.loads(raw)
        if msg.get("cmd") == "heartbeat" and msg.get("model") == "gateway":
            continue
        print(time.strftime("%H:%M:%S"), msg, flush=True)
        data = json.loads(msg.get("data", "{}"))
        if msg.get("cmd") == "report" and msg.get("model") == "switch" and data.get("status") == "click":
            t0 = time.time()
            state = toggle(light)
            print(f"  -> {light_name} {state} ({(time.time() - t0) * 1000:.0f}ms)", flush=True)


if __name__ == "__main__":
    main()
