import asyncio
import logging
import os
import time
from collections import deque

import miio

from .catalog import merge, rooms_from_homes
from .drivers.gateway2 import KIND_BY_MODEL, Gateway2, Gw2DeviceDriver, Gw2DoorbellDriver
from .drivers.miio_wifi import DRIVERS
from .micloud import MiCloud
from .rules import RuleEngine
from .store import cloud_file, devices_file, rules_file, settings_file

log = logging.getLogger(__name__)

GW2_NAMES = {"switch": "无线开关", "plug": "插座", "curtain": "窗帘"}
PUBLIC_FIELDS = ("id", "name", "room", "kind", "model", "hidden")
DRIVER_FIELDS = ("driver", "ip", "token", "sid")
CLOUD_SYNC_INTERVAL = 30 * 60
DOORBELL_ID = "gw2.doorbell"


class Hub:
    def __init__(self):
        self.records: dict[str, dict] = {r["id"]: r for r in devices_file.load()}
        self.settings: dict = settings_file.load()
        self.rules: list[dict] = rules_file.load()
        self.states: dict[str, dict] = {i: {"online": False} for i in self.records}
        self.drivers: dict = {}
        self.events: deque = deque(maxlen=200)
        self.subscribers: set[asyncio.Queue] = set()
        self.engine = RuleEngine(self)
        self.gateway: Gateway2 | None = None
        self.cloud = MiCloud(cloud_file.load())
        self.cloud_status: dict = {"last_sync": None, "last_error": None, "summary": None, "login": None}
        self._poll_tasks: dict[str, asyncio.Task] = {}
        self._tasks: list[asyncio.Task] = []
        self._sync_lock = asyncio.Lock()
        self.pairing: dict = {"until": 0.0, "found": []}
        self._pairing_task: asyncio.Task | None = None

    async def start(self) -> None:
        lan_ip = os.environ.get("HUB_LAN_IP") or self.settings.get("lan_ip", "0.0.0.0")
        gw = next((r for r in self.records.values() if r["kind"] == "gateway"), None)
        if gw:
            self.gateway = Gateway2(gw["ip"], gw["sid"], gw["lan_key"], lan_ip, self._gw_state, self._gw_event)
            await self.gateway.start()
            if DOORBELL_ID not in self.records:
                self.records[DOORBELL_ID] = {
                    "id": DOORBELL_ID, "name": "门铃", "room": gw["room"], "kind": "doorbell",
                    "model": gw["model"], "driver": "gw2bell", "hidden": False, "tone": 10, "volume": 50,
                }
                self.states[DOORBELL_ID] = {"online": False}
                self.save_devices()
        for record in self.records.values():
            self._attach(record)
        self._tasks.append(asyncio.create_task(self._cloud_loop()))

    async def stop(self) -> None:
        for task in [*self._tasks, *self._poll_tasks.values()]:
            task.cancel()

    # --- drivers & polling ---------------------------------------------
    def _attach(self, record: dict) -> None:
        driver_name = record.get("driver")
        if driver_name in ("gw2", "gw2bell"):
            if not self.gateway:
                return
            driver_cls = Gw2DoorbellDriver if driver_name == "gw2bell" else Gw2DeviceDriver
            driver = driver_cls(record, self.gateway)
        elif driver_name in DRIVERS:
            driver = DRIVERS[driver_name](record)
        else:
            return
        self.drivers[record["id"]] = driver
        self._poll_tasks[record["id"]] = asyncio.create_task(self._poll_loop(record["id"]))

    def _detach(self, device_id: str) -> None:
        task = self._poll_tasks.pop(device_id, None)
        if task:
            task.cancel()
        self.drivers.pop(device_id, None)

    async def _poll_loop(self, device_id: str) -> None:
        driver = self.drivers[device_id]
        while True:
            state = await self.refresh(device_id)
            interval = driver.poll_interval if state.get("online") else driver.offline_retry
            await asyncio.sleep(interval)

    async def refresh(self, device_id: str) -> dict:
        driver = self.drivers.get(device_id)
        if driver:
            try:
                self.update_state(device_id, {"online": True, **await driver.poll()})
            except Exception as e:
                log.debug("poll %s failed: %s", device_id, e)
                self.update_state(device_id, {"online": False})
        return self.states.get(device_id, {})

    async def command(self, device_id: str, action: str, value=None) -> dict:
        driver = self.drivers.get(device_id)
        if not driver:
            raise KeyError(device_id)
        await driver.command(action, value)
        return await self.refresh(device_id)

    def update_state(self, device_id: str, partial: dict) -> None:
        old = self.states.get(device_id, {})
        new = {**old, **partial}
        if new != old:
            self.states[device_id] = new
            self.broadcast({"type": "state", "id": device_id, "state": new})

    # --- gateway 2 callbacks ---------------------------------------------
    def _gw_state(self, sid: str, model: str, state: dict) -> None:
        device_id = f"lumi.{sid}"
        if device_id not in self.records:
            self._add_gw2_device(sid, model)
        self.update_state(device_id, state)

    def _gw_event(self, sid: str, model: str, event: str) -> None:
        device_id = f"lumi.{sid}"
        entry = {"ts": time.time(), "device": device_id, "event": event}
        self.events.append(entry)
        self.broadcast({"type": "event", **entry})
        self.engine.handle_event(device_id, event)

    def _add_gw2_device(self, sid: str, model: str) -> None:
        kind = KIND_BY_MODEL.get(model, "other")
        record = {
            "id": f"lumi.{sid}",
            "name": f"{GW2_NAMES.get(kind, model)} {sid[-4:]}",
            "room": "未分配",
            "kind": kind,
            "model": model,
            "driver": "gw2",
            "sid": sid,
            "gw_model": model,
            "hidden": False,
        }
        self.records[record["id"]] = record
        self.states.setdefault(record["id"], {"online": True})
        self.save_devices()
        self._attach(record)
        self.broadcast({"type": "devices"})
        log.info("discovered new gateway device %s (%s)", record["id"], model)

    # --- gateway 2 pairing --------------------------------------------------
    def pairing_status(self) -> dict:
        remaining = max(0, round(self.pairing["until"] - time.time()))
        return {"active": remaining > 0, "remaining": remaining, "found": self.pairing["found"]}

    def _gw_miio(self) -> "miio.Device":
        gw = next((r for r in self.records.values() if r["kind"] == "gateway"), None)
        if not gw or not gw.get("token"):
            raise RuntimeError("还没有网关 2 的密钥，请先在米家同步一次")
        if not self.gateway:
            raise RuntimeError("网关 2 未连接")
        return miio.Device(gw["ip"], gw["token"], timeout=3)

    async def gateway_children(self) -> list[dict]:
        table = await self._gw_table(self._gw_miio(), attempts=3)
        children = []
        for sid, online in table.items():
            device_id = f"lumi.{sid}"
            known = device_id in self.records
            children.append({
                "sid": sid,
                "online": online,
                "device": self.public_device(device_id) if known else None,
            })
        return children

    async def start_pairing(self, seconds: int) -> dict:
        device = self._gw_miio()
        before = await self._gw_table(device, attempts=3)
        await asyncio.to_thread(device.send, "start_zigbee_join", [seconds])
        self.pairing = {"until": time.time() + seconds, "found": []}
        if self._pairing_task:
            self._pairing_task.cancel()
        self._pairing_task = asyncio.create_task(self._watch_pairing(device, before))
        self.broadcast({"type": "pairing"})
        return self.pairing_status()

    @staticmethod
    async def _gw_table(device: "miio.Device", attempts: int = 1) -> dict[str, bool]:
        """sid -> online, straight from the gateway's sub-device table."""
        for attempt in range(attempts):
            try:
                flat = await asyncio.to_thread(device.send, "get_device_prop", ["lumi.0", "device_list"])
                break
            except Exception:
                if attempt == attempts - 1:
                    raise
        rows = [flat[i:i + 5] for i in range(0, len(flat), 5)]
        return {row[0].removeprefix("lumi."): bool(row[2]) for row in rows if row[0] != "lumi.0"}

    async def _watch_pairing(self, device: "miio.Device", before: dict[str, bool]) -> None:
        # A joined device shows up in the gateway's table before it reports anything. A device that
        # re-pairs keeps its old entry, which only flips from offline to online.
        while time.time() < self.pairing["until"] + 30:
            await asyncio.sleep(3)
            try:
                table = await self._gw_table(device)
            except Exception as e:
                log.debug("pairing poll failed: %s", e)
                continue
            joined = {sid for sid, online in table.items() if sid not in before or (online and not before[sid])}
            for sid in joined - {d.removeprefix("lumi.") for d in self.pairing["found"]}:
                log.info("device %s %s gateway 2", sid, "rejoined" if sid in before else "joined")
                try:
                    await self.gateway.read(sid)
                except Exception as e:
                    log.debug("first read of %s failed: %s", sid, e)
                if f"lumi.{sid}" not in self.records:
                    self._add_gw2_device(sid, self.gateway.models.get(sid, ""))
                self.pairing["found"].append(f"lumi.{sid}")
                self.broadcast({"type": "pairing"})
        self.broadcast({"type": "pairing"})
        if self.pairing["found"] and self.cloud.logged_in:
            try:
                await self.sync_cloud()
            except Exception as e:
                log.warning("cloud sync after pairing failed: %s", e)

    # --- Mi Home cloud sync -----------------------------------------------
    async def _cloud_loop(self) -> None:
        while True:
            if self.cloud.logged_in:
                try:
                    await self.sync_cloud()
                except Exception as e:
                    log.warning("cloud sync failed: %s", e)
            await asyncio.sleep(CLOUD_SYNC_INTERVAL)

    async def start_cloud_login(self) -> dict:
        login = self.cloud_status["login"]
        if login and login["state"] == "waiting" and self.cloud.login_pending:
            return login
        info = await asyncio.to_thread(self.cloud.start_qr_login)
        self.cloud_status["login"] = {"state": "waiting", **info}
        self._tasks.append(asyncio.create_task(self._wait_cloud_login()))
        return self.cloud_status["login"]

    async def _wait_cloud_login(self) -> None:
        login = self.cloud_status["login"]
        try:
            ok = await asyncio.to_thread(self.cloud.wait_qr_login)
        except Exception as e:
            ok = False
            login["error"] = str(e)
        login["state"] = "success" if ok else ("error" if "error" in login else "expired")
        self.broadcast({"type": "cloud"})
        if not ok:
            return
        cloud_file.save(self.cloud.data)
        try:
            await self.sync_cloud()
        except Exception as e:
            log.warning("cloud sync after login failed: %s", e)

    def logout_cloud(self) -> None:
        self.cloud.data.clear()
        cloud_file.save({})
        self.cloud_status.update(login=None, summary=None, last_error=None)

    async def sync_cloud(self) -> dict:
        async with self._sync_lock:
            try:
                homes = await asyncio.to_thread(self.cloud.fetch_homes)
            except Exception as e:
                self.cloud_status["last_error"] = str(e)
                self.broadcast({"type": "cloud"})
                raise
            finally:
                if self.cloud.data:
                    cloud_file.save(self.cloud.data)
            room_of, room_order = rooms_from_homes(homes)
            cloud_devices = [d for h in homes for d in h["devices"]]
            gw = next((r for r in self.records.values() if r["kind"] == "gateway"), {})
            records, summary = merge(cloud_devices, room_of, self.records, gw.get("id", ""), gw.get("lan_key", ""))
            self._apply_records(records)
            self.settings["rooms"] = room_order
            self.save_settings()
            self.cloud_status.update(last_sync=time.time(), last_error=None, summary=summary)
            self.broadcast({"type": "devices"})
            self.broadcast({"type": "cloud"})
            log.info("cloud sync: %s", {k: len(v) for k, v in summary.items()})
            return summary

    def _apply_records(self, records: list[dict]) -> None:
        for record in records:
            rid = record["id"]
            old = self.records.get(rid)
            self.records[rid] = record
            self.states.setdefault(rid, {"online": False})
            if record["kind"] == "gateway":
                continue
            if old is None or any(old.get(f) != record.get(f) for f in DRIVER_FIELDS):
                self._detach(rid)
                self._attach(record)
            else:
                driver = self.drivers.get(rid)
                if driver:
                    driver.record = record
        self.save_devices()

    # --- views & persistence ---------------------------------------------
    def public_device(self, device_id: str) -> dict:
        record = self.records[device_id]
        return {
            **{k: record.get(k) for k in PUBLIC_FIELDS},
            "name": record.get("local_name") or record["name"],
            "room": record.get("local_room") or record["room"],
            "cloud_name": record["name"],
            "cloud_room": record["room"],
            "name_auto": bool(record.get("name_auto")),
            "state": self.states.get(device_id, {}),
        }

    def save_devices(self) -> None:
        devices_file.save(list(self.records.values()))

    def save_rules(self) -> None:
        rules_file.save(self.rules)

    def save_settings(self) -> None:
        settings_file.save(self.settings)

    def broadcast(self, message: dict) -> None:
        for queue in list(self.subscribers):
            queue.put_nowait(message)
