import pytest

from homehub.auth import (
    BOOTSTRAP_ATTEMPTS, CODE_TTL, IP_FAILURES, Auth, PairError, TooManyAttempts, required_permission, token_hash,
    write_bootstrap_code,
)
from homehub.store import JsonFile


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(JsonFile, "__init__", lambda self, name, default: (
        setattr(self, "path", tmp_path / name), setattr(self, "default", default))[0])
    clock = Clock()
    auth = Auth(JsonFile("auth.json", {"devices": []}), tmp_path / "pairing-code.json", clock)
    return auth, clock, tmp_path


def test_bootstrap_code_pairs_first_admin_once(setup):
    auth, clock, tmp = setup
    code = write_bootstrap_code(tmp / "pairing-code.json", clock())
    device, token = auth.pair(code.lower(), "我的电脑", "192.168.1.5")
    assert device["role"] == "admin"
    assert auth.authenticate(token) is device
    assert device["token"] == token_hash(token) and token not in str(auth.devices)
    with pytest.raises(PairError):
        auth.pair(code, "again", "192.168.1.5")


def test_bootstrap_only_when_no_admin(setup):
    auth, clock, tmp = setup
    auth.ensure_bootstrap()
    assert (tmp / "pairing-code.json").exists()
    (tmp / "pairing-code.json").unlink()
    auth.devices.append({"id": "a", "role": "admin", "token": "x", "created": 0})
    auth.ensure_bootstrap()
    assert not (tmp / "pairing-code.json").exists()


def test_codes_carry_role_and_expire(setup):
    auth, clock, _ = setup
    code = auth.create_code("panel")["code"]
    device, _ = auth.pair(code, "走廊平板", "ip")
    assert device["role"] == "panel"
    late = auth.create_code("family")["code"]
    clock.t += CODE_TTL + 1
    with pytest.raises(PairError):
        auth.pair(late, "x", "ip")


def test_wrong_guesses_burn_live_codes(setup):
    auth, _, tmp = setup
    code = auth.create_code("family")["code"]
    for i in range(5):
        with pytest.raises(PairError):
            auth.pair("ZZZZZZ", "x", f"ip{i}")
    with pytest.raises(PairError):
        auth.pair(code, "x", "other")

    write_bootstrap_code(tmp / "pairing-code.json", 0 + 1_000_000)
    for i in range(BOOTSTRAP_ATTEMPTS):
        with pytest.raises(PairError):
            auth.pair("WRONG000", "x", f"b{i}")
    assert not (tmp / "pairing-code.json").exists()


def test_ip_lockout(setup):
    auth, clock, _ = setup
    for _ in range(IP_FAILURES):
        with pytest.raises(PairError):
            auth.pair("000000", "x", "evil")
    code = auth.create_code("admin")["code"]
    with pytest.raises(TooManyAttempts):
        auth.pair(code, "x", "evil")
    clock.t += 601
    assert auth.pair(auth.create_code("admin")["code"], "x", "evil")[0]["role"] == "admin"


def test_last_admin_cannot_be_removed_or_demoted(setup):
    auth, _, _ = setup
    admin, _ = auth.pair(auth.create_code("admin")["code"], "a", "ip")
    with pytest.raises(ValueError):
        auth.revoke(admin["id"])
    with pytest.raises(ValueError):
        auth.update(admin["id"], role="family")
    other, _ = auth.pair(auth.create_code("admin")["code"], "b", "ip")
    auth.revoke(admin["id"])
    assert [d["id"] for d in auth.devices] == [other["id"]]


def test_permissions():
    assert required_permission("GET", "/") is None
    assert required_permission("GET", "/assets/x.js") is None
    assert required_permission("POST", "/api/auth/pair") is None
    assert required_permission("GET", "/api/devices") == "view"
    assert required_permission("GET", "/api/ws") == "view"
    assert required_permission("POST", "/api/devices/x/command") == "control"
    assert required_permission("POST", "/api/scenes/x/run") == "control"
    assert required_permission("GET", "/api/cameras/x/ws") == "cameras"
    assert required_permission("PATCH", "/api/cameras/x") == "admin"
    assert required_permission("GET", "/api/events") == "history"
    for method, path in [("PATCH", "/api/devices/x"), ("PUT", "/api/floorplan"), ("GET", "/api/cloud"),
                         ("GET", "/api/rules"), ("POST", "/api/rules/x/run"), ("GET", "/api/auth/devices"),
                         ("POST", "/api/auth/codes"), ("GET", "/api/something-new")]:
        assert required_permission(method, path) == "admin", path
