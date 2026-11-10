import asyncio
import ipaddress
import logging
import os
import re
import time
import miio

from .camera_events import CameraEvents
from .cameras import Cameras
from .catalog import LOCAL_FIELDS, UNASSIGNED, gateway_record, merge, rooms_from_homes
from .drivers.gateway2 import KIND_BY_MODEL, Gateway2, Gw2DeviceDriver, Gw2DoorbellDriver
from .drivers.cloud import CLOUD_DRIVERS, MiotGenericDriver
from .miot_spec import device_types, load_fields
from .drivers.miio_wifi import DRIVERS
from .micloud import MiCloud
from .rules import RuleEngine
from .drivers.lockin import LockinCloud, LockinLockDriver
from .history import History
from .lockin_capture import LockinCapture
from .store import (DATA_DIR, cloud_file, devices_file, events_file, lockin_file, panels_file, rules_file, scenes_file,
                    settings_file)
from .voice import VoiceBridge

log = logging.getLogger(__name__)

GW2_NAMES = {"switch": "无线开关", "plug": "插座", "curtain": "窗帘"}
PUBLIC_FIELDS = ("id", "name", "room", "kind", "model", "hidden")
DRIVER_FIELDS = ("driver", "ip", "token", "sid", "midea_token", "device_id")
CLOUD_SYNC_INTERVAL = 30 * 60
DOORBELL_ID = "gw2.doorbell"
GW_DRIVERS = ("gw2", "gw2bell")
USAGE_KINDS = {"light", "plug", "ac", "bath_heater", "other"}
# A lost reply is routine on Wi-Fi, through the gateway and on the cloud API: only a run of failed polls
# means a device is offline, and the first misses are retried soon instead of after a full interval.
OFFLINE_AFTER_FAILURES = 3
FAILURE_RETRY = 10.0
# Gateways that speak the LAN protocol on UDP 9898 once it is enabled in Mi Home.
SUPPORTED_GATEWAYS = {"lumi.gateway.v2", "lumi.gateway.v3", "lumi.gateway.mieu01"}


def gateway_ip(gw: dict) -> str | None:
    return gw.get("ip_override") or gw.get("ip")


class Hub:
    def __init__(self):
        self.records: dict[str, dict] = {r["id"]: r for r in devices_file.load()}
        self.settings: dict = settings_file.load()
        self.rules: list[dict] = rules_file.load()
        self.panels: dict[str, list[dict]] = panels_file.load()
        self.scenes: list[dict] = scenes_file.load()
        self.states: dict[str, dict] = {i: {"online": False} for i in self.records}
        self.drivers: dict = {}
        self.history = History(DATA_DIR / "events.db")
        self.history.import_events(events_file.load())
        self.subscribers: set[asyncio.Queue] = set()
        self.engine = RuleEngine(self)
        self.gateway: Gateway2 | None = None
        self.cloud = MiCloud(cloud_file.load())
        self.cloud_status: dict = {"last_sync": None, "last_error": None, "summary": None, "login": None}
        self._poll_tasks: dict[str, asyncio.Task] = {}
        self._poll_failures: dict[str, int] = {}
        self._tasks: list[asyncio.Task] = []
        self._sync_lock = asyncio.Lock()
        self.pairing: dict = {"until": 0.0, "found": []}
        self._pairing_task: asyncio.Task | None = None
        self.lan_ip = "0.0.0.0"
        # Gateways in the Mi Home account as of the last sync, so the user can pick one.
        self.cloud_gateways: dict[str, dict] = {}
        self.voice = VoiceBridge(self)
        self.cameras = Cameras()
        self.camera_events = CameraEvents(self.cloud)
        self.lockin = LockinCloud(lockin_file.load())
        self.lockin_capture = LockinCapture(self.setup_lockin)

    async def start(self) -> None:
        self.lan_ip = os.environ.get("HUB_LAN_IP") or self.settings.get("lan_ip", "0.0.0.0")
        await self._start_gateway()
        for record in self.records.values():
            self._attach(record)
        self._tasks.append(asyncio.create_task(self._cloud_loop()))
        self._tasks.append(asyncio.create_task(self._gateway_watch()))
        self._tasks.append(asyncio.create_task(self.voice.run()))

    async def stop(self) -> None:
        for task in [*self._tasks, *self._poll_tasks.values()]:
            task.cancel()
        await self.lockin_capture.stop()
        self.history.close()
        if self.gateway:
            self.gateway.stop()

    # --- gateway connection & settings --------------------------------------
    def _gw_record(self) -> dict | None:
        return next((r for r in self.records.values() if r["kind"] == "gateway"), None)

    async def _start_gateway(self) -> None:
        gw = self._gw_record()
        self.gateway = None
        if not gw or not gateway_ip(gw):
            return
        gateway = Gateway2(gateway_ip(gw), gw["sid"], gw.get("lan_key", ""), self.lan_ip, self._gw_state, self._gw_event)
        try:
            await gateway.start()
        except OSError as e:
            log.warning("gateway %s could not start: %s", gateway_ip(gw), e)
            return
        self.gateway = gateway
        if DOORBELL_ID not in self.records:
            self.records[DOORBELL_ID] = {
                "id": DOORBELL_ID, "name": "门铃", "room": gw["room"], "kind": "doorbell",
                "model": gw["model"], "driver": "gw2bell", "hidden": False, "tone": 10, "volume": 50,
            }
            self.states[DOORBELL_ID] = {"online": False}
            self.save_devices()

    async def _restart_gateway(self) -> None:
        for rid, record in self.records.items():
            if record.get("driver") in GW_DRIVERS:
                self._detach(rid)
                self.update_state(rid, {"online": False})
        if self.gateway:
            self.gateway.stop()
        await self._start_gateway()
        for record in list(self.records.values()):
            if record.get("driver") in GW_DRIVERS:
                self._attach(record)
        self.broadcast({"type": "devices"})
        self.broadcast({"type": "gateway"})

    async def _gateway_watch(self) -> None:
        last = None
        while True:
            connected = bool(self.gateway and self.gateway.connected)
            if connected != last:
                last = connected
                self.broadcast({"type": "gateway"})
            await asyncio.sleep(5)

    def gateway_status(self) -> dict:
        gw = self._gw_record()
        children = [r for r in self.records.values() if r.get("driver") == "gw2"]
        status = {
            "configured": gw is not None,
            "connected": bool(self.gateway and self.gateway.connected),
            # Seconds ago rather than a timestamp, so a phone with a wrong clock still reads it right.
            "last_seen_ago": round(time.time() - self.gateway.last_seen) if self.gateway and self.gateway.last_seen else None,
            "children": len(children),
            "children_online": sum(1 for r in children if self.states.get(r["id"], {}).get("online")),
            "candidates": [
                {"id": did, "name": d.get("name", d["model"]), "model": d["model"], "ip": d.get("localip"),
                 "room": d["room"], "online": bool(d.get("isOnline")), "supported": d["model"] in SUPPORTED_GATEWAYS}
                for did, d in self.cloud_gateways.items()
            ],
        }
        if gw:
            status.update({
                "id": gw["id"], "name": gw.get("local_name") or gw["name"], "model": gw["model"],
                "room": gw.get("local_room") or gw["room"], "ip": gateway_ip(gw), "cloud_ip": gw.get("ip"),
                "mac": ":".join(gw["sid"][i:i + 2] for i in range(0, len(gw["sid"]), 2)).upper(),
                "has_key": bool(gw.get("lan_key")), "has_token": bool(gw.get("token")),
            })
        return status

    async def configure_gateway(self, did: str, ip: str | None = None, lan_key: str | None = None) -> dict:
        """Pick which gateway the hub talks to, and its IP / LAN key. Empty lan_key keeps the saved one."""
        if lan_key and not re.fullmatch(r"[0-9A-Za-z]{16}", lan_key):
            raise ValueError("局域网密钥应为 16 位字母或数字")
        if ip:
            try:
                ipaddress.IPv4Address(ip)
            except ValueError:
                raise ValueError("IP 地址格式不对") from None
        current = self._gw_record()
        keep = current if current and current["id"] == did else {}
        dev = self.cloud_gateways.get(did)
        if dev:
            if dev["model"] not in SUPPORTED_GATEWAYS:
                raise ValueError("这个网关不支持局域网协议，无法本地控制")
            record = gateway_record(dev, dev["room"], keep.get("lan_key", ""))
            record.update({f: keep[f] for f in LOCAL_FIELDS if f in keep})
        elif keep:
            record = dict(keep)
        else:
            raise ValueError("找不到这个网关，请先同步一次米家")
        if lan_key:
            record["lan_key"] = lan_key
        if ip is not None:
            if ip and ip != record.get("ip"):
                record["ip_override"] = ip
            else:
                record.pop("ip_override", None)
        if not gateway_ip(record):
            raise ValueError("米家没有提供这个网关的 IP，请手动填写")
        if current and current["id"] != did:
            self.records.pop(current["id"])
            self.states.pop(current["id"], None)
        self.records[did] = record
        self.states.setdefault(did, {"online": False})
        self.save_devices()
        await self._restart_gateway()
        return self.gateway_status()

    # --- drivers & polling ---------------------------------------------
    def _attach(self, record: dict) -> None:
        driver_name = record.get("driver")
        if driver_name in GW_DRIVERS:
            if not self.gateway:
                return
            driver_cls = Gw2DoorbellDriver if driver_name == "gw2bell" else Gw2DeviceDriver
            driver = driver_cls(record, self.gateway)
        elif driver_name == "cloud":
            if record.get("model") not in CLOUD_DRIVERS:
                return
            driver = CLOUD_DRIVERS[record["model"]](record, self.cloud)
        elif driver_name == "lockin":
            if not self.lockin.configured:
                return
            driver = LockinLockDriver(record, self.lockin, lambda event: self.emit_event(record["id"], event))
        elif driver_name == "midea":
            from .drivers.midea import MideaAcDriver
            driver = MideaAcDriver(record)
        elif driver_name in DRIVERS:
            driver = DRIVERS[driver_name](record)
            if driver_name == "miio" and self.cloud.logged_in:
                self._tasks.append(asyncio.create_task(self._upgrade_to_miot(record)))
        elif driver_name == "miot_cloud":
            # No LAN address: nothing to poll until the spec driver takes over through the cloud.
            if self.cloud.logged_in:
                self._tasks.append(asyncio.create_task(self._upgrade_to_miot(record)))
            return
        else:
            return
        self._start_driver(record["id"], driver)

    def _start_driver(self, device_id: str, driver) -> None:
        self.drivers[device_id] = driver
        self._poll_tasks[device_id] = asyncio.create_task(self._poll_loop(device_id))

    async def _upgrade_to_miot(self, record: dict) -> None:
        """Swap the plain online check for a driver that reads every property in the device's MIoT spec."""
        for attempt in range(5):
            try:
                fields = await asyncio.to_thread(load_fields, record["model"])
                break
            except Exception as e:
                log.debug("spec for %s unavailable: %s", record["model"], e)
                await asyncio.sleep(60 * (attempt + 1))
        else:
            return
        if not fields or self.records.get(record["id"]) is not record:
            return
        self._detach(record["id"])
        self._start_driver(record["id"], MiotGenericDriver(record, self.cloud, fields))
        self.broadcast({"type": "fields", "id": record["id"]})

    def device_fields(self, device_id: str) -> list[dict]:
        return getattr(self.drivers.get(device_id), "fields", [])

    def _detach(self, device_id: str) -> None:
        task = self._poll_tasks.pop(device_id, None)
        if task:
            task.cancel()
        self.drivers.pop(device_id, None)

    async def _poll_loop(self, device_id: str) -> None:
        driver = self.drivers[device_id]
        while True:
            state = await self.refresh(device_id)
            if not state.get("online"):
                interval = driver.offline_retry
            elif self._poll_failures.get(device_id):
                interval = min(driver.poll_interval, FAILURE_RETRY)
            else:
                interval = driver.poll_interval
            await asyncio.sleep(interval)

    async def refresh(self, device_id: str) -> dict:
        driver = self.drivers.get(device_id)
        if driver:
            try:
                state = await driver.poll()
            except Exception as e:
                failures = self._poll_failures.get(device_id, 0) + 1
                self._poll_failures[device_id] = failures
                log.debug("poll %s failed (%d in a row): %s", device_id, failures, e)
                if failures >= OFFLINE_AFTER_FAILURES:
                    self.update_state(device_id, {"online": False})
            else:
                self._poll_failures.pop(device_id, None)
                self.update_state(device_id, {"online": True, **state})
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
            self._log_power(device_id, old, new)

    def _log_power(self, device_id: str, old: dict, new: dict) -> None:
        # Offline devices keep their last power value, so only transitions seen while online count.
        record = self.records.get(device_id)
        if not record or record.get("kind") not in USAGE_KINDS or "power" not in new or not new.get("online"):
            return
        was_on = bool(old.get("power")) if old.get("online") else None
        if was_on is None or bool(new["power"]) != was_on:
            self.history.add_power(time.time(), device_id, bool(new["power"]))

    # --- gateway 2 callbacks ---------------------------------------------
    def _gw_state(self, sid: str, model: str, state: dict) -> None:
        device_id = f"lumi.{sid}"
        if device_id not in self.records:
            self._add_gw2_device(sid, model)
        self._poll_failures.pop(device_id, None)
        self.update_state(device_id, state)

    def _gw_event(self, sid: str, model: str, event: str) -> None:
        self.emit_event(f"lumi.{sid}", event)

    def emit_event(self, device_id: str, event: str) -> None:
        entry = {"ts": time.time(), "device": device_id, "event": event}
        self.history.add_event(entry["ts"], device_id, event)
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
        gw = self._gw_record()
        if not gw:
            raise RuntimeError("还没有配置网关")
        if not gw.get("token"):
            raise RuntimeError("还没有网关的设备密钥，请先在米家同步一次")
        if not self.gateway:
            raise RuntimeError("网关未连接")
        return miio.Device(gateway_ip(gw), gw["token"], timeout=3)

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
            self.cloud_gateways = {
                str(d["did"]): {**d, "room": room_of.get(str(d["did"]), UNASSIGNED)}
                for d in cloud_devices if d.get("model", "").startswith("lumi.gateway")
            }
            gw = self._gw_record() or {}
            models = sorted({d.get("model", "") for d in cloud_devices})
            try:
                spec_types = await asyncio.to_thread(device_types, models)
            except Exception as e:
                log.warning("MIoT spec index unavailable, new devices stay untyped: %s", e)
                spec_types = {}
            records, summary = merge(cloud_devices, room_of, self.records, gw.get("id", ""), gw.get("lan_key", ""),
                                     spec_types)
            if self._apply_records(records):
                await self._restart_gateway()
            self.broadcast({"type": "gateway"})
            self.settings["rooms"] = room_order
            self.save_settings()
            await self.cameras.sync(homes, room_of, str(self.cloud.data.get("user_id", "")), UNASSIGNED)
            self.cloud_status.update(last_sync=time.time(), last_error=None, summary=summary)
            self.broadcast({"type": "devices"})
            self.broadcast({"type": "cloud"})
            log.info("cloud sync: %s", {k: len(v) for k, v in summary.items()})
            return summary

    def _apply_records(self, records: list[dict]) -> bool:
        """Store merged records and reattach changed drivers. True if the gateway's address changed."""
        gateway_changed = False
        for record in records:
            rid = record["id"]
            old = self.records.get(rid)
            self.records[rid] = record
            self.states.setdefault(rid, {"online": False})
            if record["kind"] == "gateway":
                gateway_changed |= bool(old) and gateway_ip(old) != gateway_ip(record)
                continue
            if old is None or any(old.get(f) != record.get(f) for f in (*DRIVER_FIELDS, "kind")):
                self._detach(rid)
                self._attach(record)
            else:
                driver = self.drivers.get(rid)
                if driver:
                    driver.record = record
        self.save_devices()
        return gateway_changed

    # --- Midea appliances ---------------------------------------------------
    async def setup_midea(self, account: str, password: str) -> list[dict]:
        from . import midea
        records = await midea.setup(account, password)
        for record in records:
            old = self.records.get(record["id"])
            if old:
                record.update({f: old[f] for f in LOCAL_FIELDS if f in old})
        self._apply_records(records)
        self.broadcast({"type": "devices"})
        return [self.public_device(r["id"]) for r in records]

    # --- Lockin locks --------------------------------------------------------
    async def setup_lockin(self, access_token: str) -> list[dict]:
        locks = await LockinCloud({"access_token": access_token}).locks()
        if not locks:
            raise RuntimeError("这个鹿客账号下没有找到门锁")
        self.lockin.data["access_token"] = access_token
        lockin_file.save(self.lockin.data)
        records = []
        for lock in locks:
            record = {
                "id": f"lockin.{lock['uuid']}", "name": lock["name"], "room": UNASSIGNED, "kind": "lock",
                "model": f"lockin.{lock['model']}".rstrip("."), "driver": "lockin", "lockin_uuid": lock["uuid"],
                "hidden": False,
            }
            old = self.records.get(record["id"])
            if old:
                record.update({f: old[f] for f in LOCAL_FIELDS if f in old})
            self.records[record["id"]] = record
            self.states.setdefault(record["id"], {"online": False})
            self._detach(record["id"])
            self._attach(record)
            records.append(record)
        self.save_devices()
        self.broadcast({"type": "devices"})
        return [self.public_device(r["id"]) for r in records]

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
