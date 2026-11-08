"""Probe / listen to the Xiaomi Gateway 2 (lumi.gateway.v3) LAN protocol."""
import json
import socket
import struct
import sys
import time

MCAST = "224.0.0.50"
DISCOVERY_PORT = 4321
EVENT_PORT = 9898


def whois(local_ip, timeout=3.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(local_ip))
    sock.settimeout(timeout)
    sock.sendto(json.dumps({"cmd": "whois"}).encode(), (MCAST, DISCOVERY_PORT))
    try:
        data, addr = sock.recvfrom(1024)
        return addr[0], json.loads(data)
    except socket.timeout:
        return None


def send(gw_ip, payload, timeout=3.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    sock.sendto(json.dumps(payload).encode(), (gw_ip, EVENT_PORT))
    try:
        return json.loads(sock.recvfrom(4096)[0])
    except socket.timeout:
        return None


def listen(seconds, local_ip):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", EVENT_PORT))
    mreq = struct.pack("4s4s", socket.inet_aton(MCAST), socket.inet_aton(local_ip))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.settimeout(1)
    end = time.time() + seconds
    while time.time() < end:
        try:
            data, addr = sock.recvfrom(4096)
        except socket.timeout:
            continue
        print(time.strftime("%H:%M:%S"), addr[0], data.decode(errors="replace"), flush=True)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if mode == "probe":
        found = whois(sys.argv[2])
        print("whois:", found)
        if found:
            ip = found[0]
            print("discovery:", send(ip, {"cmd": "discovery"}))
    elif mode == "listen":
        listen(int(sys.argv[2]), sys.argv[3])
