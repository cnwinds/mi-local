import asyncio

import pytest

from homehub import hub as hub_module
from homehub.store import devices_file, settings_file

CLOUD_GW = {"did": "100000001", "name": "多功能网关", "model": "lumi.gateway.v3", "localip": "192.168.1.120",
            "token": "t" * 32, "mac": "04:CF:8C:00:00:01", "isOnline": True, "room": "客厅"}
MULTIMODE = {"did": "999", "name": "多模网关", "model": "lumi.gateway.mgl03", "localip": "192.168.1.9",
             "mac": "AA:BB:CC:DD:EE:FF", "isOnline": True, "room": "客厅"}


@pytest.fixture
def hub(tmp_path, monkeypatch):
    monkeypatch.setattr(devices_file, "path", tmp_path / "devices.json")
    monkeypatch.setattr(settings_file, "path", tmp_path / "settings.json")
    h = hub_module.Hub()
    h.restarts = 0

    async def fake_restart():
        h.restarts += 1

    h._restart_gateway = fake_restart
    h.cloud_gateways = {"100000001": CLOUD_GW, "999": MULTIMODE}
    return h


def test_unconfigured_status_lists_candidates(hub):
    status = hub.gateway_status()
    assert status["configured"] is False and status["connected"] is False
    support = {c["id"]: c["supported"] for c in status["candidates"]}
    assert support == {"100000001": True, "999": False}


def test_configure_picks_gateway_and_keeps_key_when_blank(hub):
    status = asyncio.run(hub.configure_gateway("100000001", lan_key="abcdEFGH12345678"))
    assert status["configured"] and status["has_key"] and status["ip"] == "192.168.1.120"
    assert status["mac"] == "04:CF:8C:00:00:01"
    assert "lan_key" not in status
    status = asyncio.run(hub.configure_gateway("100000001", ip="192.168.1.121", lan_key=""))
    assert status["ip"] == "192.168.1.121" and status["cloud_ip"] == "192.168.1.120"
    assert hub.records["100000001"]["lan_key"] == "abcdEFGH12345678"
    assert hub.restarts == 2
    # Typing the cloud IP back clears the override.
    asyncio.run(hub.configure_gateway("100000001", ip="192.168.1.120"))
    assert "ip_override" not in hub.records["100000001"]


def test_configure_rejects_bad_input(hub):
    with pytest.raises(ValueError, match="16"):
        asyncio.run(hub.configure_gateway("100000001", lan_key="short"))
    with pytest.raises(ValueError, match="IP"):
        asyncio.run(hub.configure_gateway("100000001", ip="192.168.3"))
    with pytest.raises(ValueError, match="不支持"):
        asyncio.run(hub.configure_gateway("999"))
    with pytest.raises(ValueError, match="同步"):
        asyncio.run(hub.configure_gateway("nope"))


def test_switching_gateway_replaces_the_old_record(hub):
    asyncio.run(hub.configure_gateway("100000001", lan_key="abcdEFGH12345678"))
    other = {**CLOUD_GW, "did": "555", "mac": "11:22:33:44:55:66", "localip": "192.168.1.50"}
    hub.cloud_gateways["555"] = other
    status = asyncio.run(hub.configure_gateway("555"))
    assert status["id"] == "555" and not status["has_key"]
    assert [r["id"] for r in hub.records.values() if r["kind"] == "gateway"] == ["555"]
