import asyncio
import io
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import requests
import segno
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.datastructures import Headers
from starlette.requests import cookie_parser

from .auth import COOKIE, COOKIE_MAX_AGE, PERMISSIONS, Auth, PairError, TooManyAttempts, required_permission
from .cameras import go2rtc_accounts, go2rtc_login, relay, stream_name
from .hub import Hub
from .lockin_capture import ca_pem
from .micloud import CloudError
from .ranges import byte_range
from .store import DATA_DIR, floorplan_file, panels_file, scenes_file

log = logging.getLogger(__name__)
hub = Hub()
auth = Auth()
STATIC_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await hub.start()
    auth.ensure_bootstrap()
    yield
    await hub.stop()


# No /docs or /openapi.json: they sit outside /api, where pairing is not required.
app = FastAPI(title="HomeHub", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


def _client_ip(scope) -> str:
    client = scope.get("client")
    return client[0] if client else ""


def _same_origin(headers: Headers) -> bool:
    """Blocks pages on other sites from driving the hub through a paired browser."""
    origin = headers.get("origin")
    if not origin:
        return True
    return origin.split("://", 1)[-1].rstrip("/") == headers.get("host", "")


async def _deny(scope, receive, send, status: int, detail: str) -> None:
    headers = Headers(scope=scope)
    if scope["type"] == "websocket" or status == 403:
        log.info("refused %s %s: %s (origin=%s host=%s cookie=%s ua=%s)", scope["type"], scope["path"], detail,
                 headers.get("origin"), headers.get("host"), COOKIE in headers.get("cookie", ""),
                 headers.get("user-agent", "")[:80])
    if scope["type"] == "websocket":
        await receive()
        await send({"type": "websocket.close", "code": 4401 if status == 401 else 4403})
        return
    await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)


class AuthMiddleware:
    """Checks every HTTP request and WebSocket against the paired devices and their roles."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        method = scope.get("method", "GET")
        headers = Headers(scope=scope)
        if (scope["type"] == "websocket" or method in UNSAFE_METHODS) and not _same_origin(headers):
            return await _deny(scope, receive, send, 403, "不接受来自其他网站的请求")
        need = required_permission(method, scope["path"])
        if need is None:
            return await self.app(scope, receive, send)
        device = auth.authenticate(cookie_parser(headers.get("cookie", "")).get(COOKIE, ""), _client_ip(scope))
        if not device:
            return await _deny(scope, receive, send, 401, "这台设备还没有配对")
        if need not in PERMISSIONS[device["role"]]:
            return await _deny(scope, receive, send, 403, "这台设备没有这个权限")
        scope.setdefault("state", {})["device"] = device
        await self.app(scope, receive, send)


app.add_middleware(AuthMiddleware)


class PairBody(BaseModel):
    code: str = Field(min_length=4, max_length=20)
    name: str = Field("", max_length=40)


class CodeRequest(BaseModel):
    role: Literal["admin", "family", "panel"]


class AuthDevicePatch(BaseModel):
    name: str | None = Field(None, max_length=40)
    role: Literal["admin", "family", "panel"] | None = None


# Live /api/ws queues by paired device, so revoking a device also cuts its push channel.
ws_sessions: dict[asyncio.Queue, str] = {}


def _current(request: Request) -> dict:
    return request.state.device


@app.get("/api/auth/me")
def auth_me(request: Request):
    device = auth.authenticate(request.cookies.get(COOKIE, ""), _client_ip(request.scope))
    if not device:
        return {"paired": False, "claimable": auth.claimable}
    return {"paired": True, **auth.public(device, device["id"])}


def _paired(device: dict, token: str, response: Response) -> dict:
    response.set_cookie(COOKIE, token, max_age=COOKIE_MAX_AGE, httponly=True, samesite="strict", path="/")
    return {"paired": True, **auth.public(device, device["id"])}


@app.post("/api/auth/pair")
def auth_pair(body: PairBody, request: Request, response: Response):
    try:
        device, token = auth.pair(body.code, body.name, _client_ip(request.scope))
    except TooManyAttempts:
        raise HTTPException(429, "试错次数太多，请 10 分钟后再试")
    except PairError as e:
        raise HTTPException(400, str(e))
    return _paired(device, token, response)


class ClaimBody(BaseModel):
    name: str = Field("", max_length=40)


@app.post("/api/auth/claim")
def auth_claim(body: ClaimBody, request: Request, response: Response):
    try:
        device, token = auth.claim(body.name, _client_ip(request.scope))
    except PairError as e:
        raise HTTPException(400, str(e))
    return _paired(device, token, response)


@app.get("/api/auth/devices")
def auth_devices(request: Request):
    me = _current(request)["id"]
    return [auth.public(d, me) for d in auth.devices]


@app.post("/api/auth/codes")
def auth_code(body: CodeRequest):
    return auth.create_code(body.role)


@app.patch("/api/auth/devices/{device_id}")
def auth_update(device_id: str, patch: AuthDevicePatch, request: Request):
    try:
        device = auth.update(device_id, patch.name, patch.role)
    except KeyError:
        raise HTTPException(404, "没有这台设备")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return auth.public(device, _current(request)["id"])


@app.delete("/api/auth/devices/{device_id}")
def auth_revoke(device_id: str, request: Request, response: Response):
    try:
        auth.revoke(device_id)
    except KeyError:
        raise HTTPException(404, "没有这台设备")
    except ValueError as e:
        raise HTTPException(400, str(e))
    for queue, owner in list(ws_sessions.items()):
        if owner == device_id:
            queue.put_nowait(None)
    if device_id == _current(request)["id"]:
        response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


class DevicePatch(BaseModel):
    name: str | None = None
    room: str | None = None
    hidden: bool | None = None
    local_name: str | None = None
    local_room: str | None = None
    name_auto: bool | None = None


class Command(BaseModel):
    action: str
    value: Any = None


class Trigger(BaseModel):
    type: Literal["device_event"] = "device_event"
    device: str
    event: str


class Action(BaseModel):
    device: str
    action: str
    value: Any = None


class Rule(BaseModel):
    name: str
    enabled: bool = True
    trigger: Trigger
    actions: list[Action]


def _device_or_404(device_id: str) -> dict:
    if device_id not in hub.records:
        raise HTTPException(404, "device not found")
    return hub.records[device_id]


@app.get("/api/devices")
def list_devices():
    return [hub.public_device(i) for i in hub.records]


@app.patch("/api/devices/{device_id}")
def patch_device(device_id: str, patch: DevicePatch):
    record = _device_or_404(device_id)
    record.update(patch.model_dump(exclude_unset=True))
    hub.save_devices()
    hub.broadcast({"type": "devices"})
    return hub.public_device(device_id)


@app.get("/api/devices/{device_id}/fields")
def device_fields(device_id: str):
    _device_or_404(device_id)
    return hub.device_fields(device_id)


@app.post("/api/devices/{device_id}/command")
async def device_command(device_id: str, cmd: Command):
    _device_or_404(device_id)
    try:
        state = await hub.command(device_id, cmd.action, cmd.value)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"device error: {e}")
    return state


@app.get("/api/rooms")
def list_rooms():
    rooms = list(hub.settings.get("rooms", []))
    for record in hub.records.values():
        room = record.get("local_room") or record.get("room")
        if room and room not in rooms:
            rooms.append(room)
    return rooms


@app.put("/api/rooms")
def set_rooms(rooms: list[str]):
    hub.settings["rooms"] = rooms
    hub.save_settings()
    return rooms


@app.get("/api/rules")
def list_rules():
    return hub.rules


@app.post("/api/rules")
def create_rule(rule: Rule):
    data = {"id": uuid.uuid4().hex[:8], **rule.model_dump()}
    hub.rules.append(data)
    hub.save_rules()
    return data


def _rule_index(rule_id: str) -> int:
    for i, rule in enumerate(hub.rules):
        if rule["id"] == rule_id:
            return i
    raise HTTPException(404, "rule not found")


@app.put("/api/rules/{rule_id}")
def update_rule(rule_id: str, rule: Rule):
    i = _rule_index(rule_id)
    hub.rules[i] = {"id": rule_id, **rule.model_dump()}
    hub.save_rules()
    return hub.rules[i]


@app.delete("/api/rules/{rule_id}")
def delete_rule(rule_id: str):
    hub.rules.pop(_rule_index(rule_id))
    hub.save_rules()
    return {"ok": True}


@app.post("/api/rules/{rule_id}/run")
async def run_rule(rule_id: str):
    await hub.engine.run(hub.rules[_rule_index(rule_id)])
    return {"ok": True}


class PanelItem(BaseModel):
    id: str
    size: Literal["large", "small", "hidden"]


class Scene(BaseModel):
    room: str
    name: str = Field(min_length=1, max_length=12)
    icon: str = "⭐"
    actions: list[Action]


@app.get("/api/panels")
def list_panels():
    return hub.panels


@app.put("/api/panels/{room}")
def set_panel(room: str, layout: list[PanelItem]):
    hub.panels[room] = [item.model_dump() for item in layout]
    panels_file.save(hub.panels)
    hub.broadcast({"type": "panels"})
    return hub.panels[room]


Point = tuple[float, float]


class FloorRoom(BaseModel):
    name: str = Field(min_length=1)
    points: list[Point] = Field(min_length=3)
    label: Point | None = None
    outdoor: bool = False


class FloorBackground(BaseModel):
    """The uploaded floor plan image: its top left corner at (x, y), w × h in plan units."""
    x: float = 0
    y: float = 0
    w: float = Field(gt=0)
    h: float = Field(gt=0)
    opacity: float = Field(0.35, ge=0, le=1)


class Floorplan(BaseModel):
    view: tuple[float, float, float, float]
    rooms: list[FloorRoom]
    devices: dict[str, Point] = {}
    cameras: dict[str, Point] = {}
    background: FloorBackground | None = None


BACKGROUND_FILE = DATA_DIR / "floorplan-bg"
BACKGROUND_MAX = 15 * 1024 * 1024


@app.get("/api/floorplan")
def get_floorplan():
    return floorplan_file.load()


@app.put("/api/floorplan/background")
async def set_floorplan_background(request: Request):
    media_type = request.headers.get("content-type", "")
    if media_type not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
        raise HTTPException(400, "只支持 PNG、JPG、WebP 或 GIF 图片")
    body = await request.body()
    if not body or len(body) > BACKGROUND_MAX:
        raise HTTPException(413, "图片太大，最多 15 MB")
    BACKGROUND_FILE.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(BACKGROUND_FILE.write_bytes, body)
    BACKGROUND_FILE.with_suffix(".type").write_text(media_type)
    return {"ok": True}


@app.get("/api/floorplan/background")
def get_floorplan_background():
    if not BACKGROUND_FILE.exists():
        raise HTTPException(404, "没有户型底图")
    type_file = BACKGROUND_FILE.with_suffix(".type")
    media_type = type_file.read_text() if type_file.exists() else "image/png"
    return FileResponse(BACKGROUND_FILE, media_type=media_type, headers={"Cache-Control": "private, no-cache"})


@app.delete("/api/floorplan/background")
def delete_floorplan_background():
    BACKGROUND_FILE.unlink(missing_ok=True)
    BACKGROUND_FILE.with_suffix(".type").unlink(missing_ok=True)
    return {"ok": True}


@app.put("/api/floorplan")
def set_floorplan(plan: Floorplan):
    data = plan.model_dump()
    floorplan_file.save(data)
    hub.broadcast({"type": "floorplan"})
    return data


@app.get("/api/scenes")
def list_scenes():
    return hub.scenes


def _scene_index(scene_id: str) -> int:
    for i, scene in enumerate(hub.scenes):
        if scene["id"] == scene_id:
            return i
    raise HTTPException(404, "scene not found")


def _save_scenes() -> None:
    scenes_file.save(hub.scenes)
    hub.broadcast({"type": "scenes"})


@app.post("/api/scenes")
def create_scene(scene: Scene):
    data = {"id": uuid.uuid4().hex[:8], **scene.model_dump()}
    hub.scenes.append(data)
    _save_scenes()
    return data


@app.put("/api/scenes/{scene_id}")
def update_scene(scene_id: str, scene: Scene):
    i = _scene_index(scene_id)
    hub.scenes[i] = {"id": scene_id, **scene.model_dump()}
    _save_scenes()
    return hub.scenes[i]


@app.delete("/api/scenes/{scene_id}")
def delete_scene(scene_id: str):
    hub.scenes.pop(_scene_index(scene_id))
    _save_scenes()
    return {"ok": True}


@app.post("/api/scenes/{scene_id}/run")
async def run_scene(scene_id: str):
    await hub.engine.run(hub.scenes[_scene_index(scene_id)])
    return {"ok": True}


@app.get("/api/cloud")
def cloud_status():
    return {"logged_in": hub.cloud.logged_in, "user_id": hub.cloud.data.get("user_id"), "region": hub.cloud.region,
            **hub.cloud_status}


class CloudLoginRequest(BaseModel):
    region: Literal["cn", "sg", "de", "us", "ru", "i2"] = "cn"


@app.post("/api/cloud/login")
async def cloud_login(body: CloudLoginRequest | None = None):
    try:
        return await hub.start_cloud_login((body or CloudLoginRequest()).region)
    except Exception as e:
        raise HTTPException(502, f"无法连接小米账号服务：{e}")


@app.post("/api/cloud/sync")
async def cloud_sync():
    if not hub.cloud.logged_in:
        raise HTTPException(400, "未登录米家账号")
    try:
        return await hub.sync_cloud()
    except Exception as e:
        raise HTTPException(502, f"同步失败：{e}")


@app.post("/api/cloud/logout")
def cloud_logout():
    hub.logout_cloud()
    return {"ok": True}


class GatewayConfig(BaseModel):
    id: str
    ip: str | None = None
    lan_key: str | None = None


@app.get("/api/gateway")
def gateway_status():
    return hub.gateway_status()


@app.put("/api/gateway")
async def configure_gateway(config: GatewayConfig):
    try:
        return await hub.configure_gateway(config.id, config.ip, config.lan_key)
    except ValueError as e:
        raise HTTPException(400, str(e))


class PairingRequest(BaseModel):
    seconds: int = Field(120, ge=10, le=300)


@app.get("/api/gateway/pairing")
def pairing_status():
    return hub.pairing_status()


@app.post("/api/gateway/pairing")
async def start_pairing(req: PairingRequest):
    try:
        return await hub.start_pairing(req.seconds)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"网关没有响应：{e}")


@app.get("/api/gateway/children")
async def gateway_children():
    try:
        return await hub.gateway_children()
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"网关没有响应：{e}")


class MideaLogin(BaseModel):
    account: str = Field(min_length=1)
    password: str = Field(min_length=1)


@app.post("/api/midea/setup")
async def midea_setup(login: MideaLogin):
    try:
        return await hub.setup_midea(login.account, login.password)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"接入失败：{e}")


class LockinLogin(BaseModel):
    access_token: str = Field(min_length=20)


@app.get("/api/lockin")
def lockin_status():
    return {"configured": hub.lockin.configured, "capture": hub.lockin_capture.status()}


class CaptureToggle(BaseModel):
    active: bool


@app.post("/api/lockin/capture")
async def lockin_capture(body: CaptureToggle):
    if body.active:
        try:
            await hub.lockin_capture.start()
        except OSError as e:
            raise HTTPException(500, f"代理端口打不开：{e}")
    else:
        await hub.lockin_capture.stop()
    return hub.lockin_capture.status()


@app.get("/api/lockin/ca.crt")
async def lockin_ca():
    pem = await asyncio.to_thread(ca_pem)
    return Response(pem, media_type="application/x-x509-ca-cert",
                    headers={"Content-Disposition": 'attachment; filename="mi-local-ca.crt"'})


@app.get("/api/qr.svg")
def qr_svg(text: str):
    buf = io.BytesIO()
    segno.make(text, error="m").save(buf, kind="svg", scale=6, border=2, dark="#14161b", light="#ffffff")
    return Response(buf.getvalue(), media_type="image/svg+xml")


@app.post("/api/lockin/setup")
async def lockin_setup(login: LockinLogin):
    try:
        return await hub.setup_lockin(login.access_token.strip())
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"连不上鹿客云：{e}")


class VoiceConfig(BaseModel):
    enabled: bool


@app.get("/api/voice")
def voice_status():
    return hub.voice.public_status()


@app.put("/api/voice")
def set_voice(config: VoiceConfig):
    hub.settings["voice_bridge"] = config.enabled
    hub.save_settings()
    hub.broadcast({"type": "voice"})
    return hub.voice.public_status()


@app.get("/api/events")
async def list_events(before: float | None = None, limit: int = 100):
    return await asyncio.to_thread(hub.history.events, before, min(max(limit, 1), 500))


@app.get("/api/stats")
async def stats(days: int | None = None, tz: int = 0):
    kinds = {i: r.get("kind", "") for i, r in hub.records.items()}
    return await asyncio.to_thread(hub.history.stats, days, tz, kinds)


@app.get("/api/cameras")
def list_cameras():
    return hub.cameras.public()


class Go2rtcLogin(BaseModel):
    username: str | None = Field(None, max_length=100)
    password: str | None = Field(None, max_length=200)
    captcha: str | None = Field(None, max_length=20)
    verify: str | None = Field(None, max_length=20)


@app.get("/api/go2rtc")
async def go2rtc_status():
    """Whether go2rtc runs, and is logged in with the account the camera streams are registered under."""
    accounts = await asyncio.to_thread(go2rtc_accounts)
    user = str(hub.cloud.data.get("user_id") or "")
    return {
        "running": accounts is not None,
        "logged_in": bool(accounts) and (not user or user in accounts),
        "other_account": bool(accounts) and bool(user) and user not in accounts,
    }


async def _sync_quietly() -> None:
    try:
        await hub.sync_cloud()
    except Exception as e:
        log.info("sync after the camera login failed: %s", e)


@app.post("/api/go2rtc/login")
async def go2rtc_login_step(body: Go2rtcLogin):
    fields = {k: v.strip() for k, v in body.model_dump().items() if v and v.strip()}
    if not fields:
        raise HTTPException(400, "请填写账号和密码")
    try:
        result = await asyncio.to_thread(go2rtc_login, fields)
    except requests.RequestException:
        raise HTTPException(502, "监控服务（go2rtc）没有运行")
    except ValueError as e:
        raise HTTPException(400, str(e))
    # Register the camera streams under the fresh login right away.
    if result.get("ok") and hub.cloud.logged_in:
        task = asyncio.create_task(_sync_quietly())
        _background.add(task)
        task.add_done_callback(_background.discard)
    return result


_background: set[asyncio.Task] = set()


class CameraUpdate(BaseModel):
    hidden: bool | None = None
    unsupported: bool | None = None


@app.patch("/api/cameras/{camera_id}")
def update_camera(camera_id: str, body: CameraUpdate):
    try:
        hub.cameras.update(camera_id, **body.model_dump(exclude_none=True))
    except KeyError:
        raise HTTPException(404, "没有这个摄像头")
    return hub.cameras.public()


def _camera(camera_id: str) -> dict:
    camera = hub.cameras.get(camera_id)
    if not camera:
        raise HTTPException(404, "没有这个摄像头")
    return camera


async def _cloud_media(fn, *args):
    if not hub.cloud.logged_in:
        raise HTTPException(409, "还没有登录米家账号")
    try:
        return await asyncio.to_thread(fn, *args)
    except KeyError:
        raise HTTPException(404, "没有这条记录，刷新列表再试")
    except (CloudError, requests.RequestException, ValueError) as e:
        raise HTTPException(502, f"米家云暂时取不到：{e}")


def _ranged(request: Request, body: bytes, media_type: str) -> Response:
    """Byte ranges matter: Safari will not play an <video> source that ignores them."""
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=86400"}
    size = len(body)
    try:
        span = byte_range(request.headers.get("range", ""), size)
    except ValueError:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
    if not span:
        return Response(body, media_type=media_type, headers=headers)
    start, end = span
    return Response(body[start:end + 1], status_code=206, media_type=media_type,
                    headers={**headers, "Content-Range": f"bytes {start}-{end}/{size}"})


@app.get("/api/cameras/{camera_id}/events")
async def camera_events(camera_id: str, before: int | None = None, limit: int = 30):
    return await _cloud_media(hub.camera_events.list, _camera(camera_id), before, min(max(limit, 1), 50))


@app.get("/api/cameras/{camera_id}/events/{file_id}/thumb.jpg")
async def camera_event_thumb(camera_id: str, file_id: str, request: Request, t: int | None = None):
    image = await _cloud_media(hub.camera_events.thumbnail, _camera(camera_id), file_id, t)
    return _ranged(request, image, "image/jpeg")


@app.get("/api/cameras/{camera_id}/events/{file_id}/clip")
async def camera_event_clip(camera_id: str, file_id: str):
    return await _cloud_media(hub.camera_events.clip, _camera(camera_id), file_id)


@app.get("/api/cameras/{camera_id}/events/{file_id}/clip/{index}.mp4")
async def camera_event_clip_part(camera_id: str, file_id: str, index: int, request: Request):
    video = await _cloud_media(hub.camera_events.clip_part, _camera(camera_id), file_id, index)
    return _ranged(request, video, "video/mp4")


@app.websocket("/api/cameras/{camera_id}/ws")
async def camera_stream(ws: WebSocket, camera_id: str, quality: Literal["sd", "hd", "hd3"] = "sd"):
    if not hub.cameras.get(camera_id):
        await ws.close(code=4404)
        return
    await ws.accept()
    await relay(ws, stream_name(camera_id, quality), lambda: hub.cameras.update(camera_id, unsupported=True))
    try:
        await ws.close()
    except RuntimeError:
        pass


@app.websocket("/api/ws")
async def websocket(ws: WebSocket):
    await ws.accept()
    queue: asyncio.Queue = asyncio.Queue()
    hub.subscribers.add(queue)
    ws_sessions[queue] = ws.scope["state"]["device"]["id"]
    try:
        while (message := await queue.get()) is not None:
            await ws.send_json(message)
        await ws.close(code=4401)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.subscribers.discard(queue)
        ws_sessions.pop(queue, None)


if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        file = STATIC_DIR / path
        if path and file.is_file():
            return FileResponse(file)
        return FileResponse(STATIC_DIR / "index.html")
