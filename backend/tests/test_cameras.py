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


def test_source_urls():
    camera = {"id": "100000003", "ip": "192.168.1.156", "model": "chuangmi.camera.ipc009"}
    hd = "xiaomi://10001:cn@192.168.1.156?did=100000003&model=chuangmi.camera.ipc009"
    assert source(camera, "10001", "hd") == hd
    assert source(camera, "10001", "sd") == hd + "&subtype=sd"
    assert stream_name("100000003", "sd") == "cam_100000003_sd"


def test_register_only_touches_changed_streams(monkeypatch):
    cam = cameras.Cameras.__new__(cameras.Cameras)
    cam.items = [{"id": "1", "ip": "192.168.1.5", "model": "isa.camera.hlc7"}]
    current = {"cam_1_hd": {"producers": [{"url": source(cam.items[0], "9", "hd")}]},
               "cam_1_sd": {"producers": [{"url": "xiaomi://9:cn@192.168.1.4?did=1&model=isa.camera.hlc7&subtype=sd"}]}}
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
    assert calls == [("PATCH", "cam_1_sd")]
