"""Discover Xiaomi miIO devices on the LAN and probe gateway ports."""
import ipaddress
import json
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HELLO = bytes.fromhex("21310020" + "ff" * 28)
MIIO_PORT = 54321
PROBE_PORTS = [23, 1883, 80, 8080, 554, 6668]


def miio_hello(subnet: str, timeout: float = 3.0) -> dict:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.3)
    if hasattr(socket, "SIO_UDP_CONNRESET"):
        sock.ioctl(socket.SIO_UDP_CONNRESET, False)
    net = ipaddress.ip_network(subnet, strict=False)
    sock.sendto(HELLO, (str(net.broadcast_address), MIIO_PORT))
    for host in net.hosts():
        sock.sendto(HELLO, (str(host), MIIO_PORT))
    found = {}
    end = time.time() + timeout
    while time.time() < end:
        try:
            data, (ip, _) = sock.recvfrom(1024)
        except (socket.timeout, ConnectionResetError):
            continue
        if len(data) == 32 and data[:2] == b"\x21\x31":
            did = int.from_bytes(data[8:12], "big")
            stamp = int.from_bytes(data[12:16], "big")
            found[ip] = {"did": did, "uptime_s": stamp}
    return found


def tcp_open(ip: str, port: int) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=0.6):
            return True
    except OSError:
        return False


def probe_ports(ips):
    result = {}
    with ThreadPoolExecutor(64) as pool:
        jobs = {(ip, p): pool.submit(tcp_open, ip, p) for ip in ips for p in PROBE_PORTS}
    for (ip, p), fut in jobs.items():
        if fut.result():
            result.setdefault(ip, []).append(p)
    return result


if __name__ == "__main__":
    subnet = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.0/24"
    devices = miio_hello(subnet)
    hosts = [str(h) for h in ipaddress.ip_network(subnet, strict=False).hosts()]
    ports = probe_ports(hosts)
    print(json.dumps({"miio": devices, "open_ports": ports}, indent=2))
