import asyncio
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .hub import Hub
from .store import panels_file, scenes_file

hub = Hub()
STATIC_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await hub.start()
    yield
    await hub.stop()


app = FastAPI(title="HomeHub", lifespan=lifespan)


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
    return {"logged_in": hub.cloud.logged_in, "user_id": hub.cloud.data.get("user_id"), **hub.cloud_status}


@app.post("/api/cloud/login")
async def cloud_login():
    try:
        return await hub.start_cloud_login()
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


@app.get("/api/events")
def list_events():
    return list(hub.events)


@app.websocket("/api/ws")
async def websocket(ws: WebSocket):
    await ws.accept()
    queue: asyncio.Queue = asyncio.Queue()
    hub.subscribers.add(queue)
    try:
        while True:
            await ws.send_json(await queue.get())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.subscribers.discard(queue)


if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        file = STATIC_DIR / path
        if path and file.is_file():
            return FileResponse(file)
        return FileResponse(STATIC_DIR / "index.html")
