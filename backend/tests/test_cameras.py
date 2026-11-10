import pytest
from homehub import cameras
from homehub.cameras import from_homes, source, stream_name

HOMES = [{"devices": [
    {"did": "100000003", "name": "摄像机 儿童房", "model": "chuangmi.camera.ipc009", "localip": "192.168.1.156"},
    {"did": "100000004", "name": "户外", "model": "xiaovv.camera.p1", "localip": "192.168.1.111"},
    {"did": "77", "name": "灯", "model": "yeelink.light.ceiling22", "localip": "192.168.1.20"},
    {"did": "88", "name": "离线摄像头", "model": "isa.camera.hlc7", "localip": ""},
]}]


def test_only_reachable_cameras_are_listed_and_hidden_flag_survives():
    existing = [{"id": "100000003", "hidden": True}]
    result = from_homes(HOMES, {"100000003": "儿童房"}, existing, "未分配")
    assert [(c["id"], c["room"], c["hidden"]) for c in result] == [("100000003", "儿童房", True),
                                                                     ("100000004", "未分配", False)]


def test_unsupported_mark_survives_sync():
    existing = [{"id": "100000004", "unsupported": True}]
    result = from_homes(HOMES, {}, existing, "未分配")
    assert [c.get("unsupported", False) for c in result] == [False, True]


def test_source_urls():
    camera = {"id": "100000003", "ip": "192.168.1.156", "model": "chuangmi.camera.ipc009"}
    hd = "xiaomi://10001:cn@192.168.1.156?did=100000003&model=chuangmi.camera.ipc009"
    assert source(camera, "10001", "hd") == hd
    assert source(camera, "10001", "sd") == hd + "&subtype=sd"
    assert source(camera, "10001", "hd3") == hd + "&subtype=3"
    assert stream_name("100000003", "sd") == "cam_100000003_sd"


def test_register_only_touches_changed_streams(monkeypatch):
    cam = cameras.Cameras.__new__(cameras.Cameras)
    cam.items = [{"id": "1", "ip": "192.168.1.5", "model": "isa.camera.hlc7"}]
    # go2rtc masks the account part of every source URL it reports
    current = {"cam_1_hd": {"producers": [{"url": "xiaomi://***@192.168.1.5?did=1&model=isa.camera.hlc7"}]},
               "cam_1_sd": {"producers": [{"url": "xiaomi://***@192.168.1.4?did=1&model=isa.camera.hlc7&subtype=sd"}]}}
    calls = []

    class Response:
        def json(self):
            return current

        def raise_for_status(self):
            pass

    monkeypatch.setattr(cameras.requests, "get", lambda url, timeout: Response())
    monkeypatch.setattr(cameras.requests, "request",
                        lambda method, url, params, timeout: calls.append((method, params["name"])) or Response())
    cam._register("9")
    assert calls == [("PATCH", "cam_1_sd"), ("PUT", "cam_1_hd3")]


class FakeResponse:
    def __init__(self, status, body):
        self.status_code, self._body = status, body
        self.ok = status < 400
        self.text = body if isinstance(body, str) else ""
        self.reason = "x"

    def json(self):
        return self._body


def test_go2rtc_login_steps(monkeypatch):
    sent = []
    replies = iter([FakeResponse(401, {"captcha": "aW1n"}), FakeResponse(401, {"verify_phone": "138****0000"}),
                    FakeResponse(200, ""), FakeResponse(500, 'xiaomi: {"code":70016}')])
    monkeypatch.setattr(cameras.requests, "post", lambda url, data, timeout: sent.append(data) or next(replies))
    assert cameras.go2rtc_login({"username": "u", "password": "p"}) == {"captcha": "aW1n"}
    assert cameras.go2rtc_login({"captcha": "abcd"}) == {"verify": "138****0000"}
    assert cameras.go2rtc_login({"verify": "123456"}) == {"ok": True}
    with pytest.raises(ValueError, match="账号或密码不对"):
        cameras.go2rtc_login({"username": "u", "password": "bad"})
    assert sent[1] == {"captcha": "abcd"}


def test_region_picks_the_api_server():
    from homehub.micloud import MiCloud, api_base
    assert api_base("cn") == "https://api.io.mi.com/app"
    assert api_base("sg") == "https://sg.api.io.mi.com/app"
    assert MiCloud({}).region == "cn" and MiCloud({"region": "de"}).region == "de"
    assert source({"id": "1", "ip": "10.0.0.2", "model": "x.camera.y"}, "42", "hd", "sg").startswith("xiaomi://42:sg@")
