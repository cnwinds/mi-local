"""Permanent event history in SQLite, plus the usage statistics drawn from it.

Two append-only tables: `events` (switch presses, lock and door events) and `power` (every on/off
transition of a device, which is what usage time is computed from). Nothing is ever pruned.
"""
import sqlite3
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, ts REAL NOT NULL, device TEXT NOT NULL, event TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS events_ts ON events (ts);
CREATE TABLE IF NOT EXISTS power (id INTEGER PRIMARY KEY, ts REAL NOT NULL, device TEXT NOT NULL, is_on INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS power_device_ts ON power (device, ts);
CREATE INDEX IF NOT EXISTS power_ts ON power (ts);
"""
PRESS_EVENTS = ("click", "double_click", "long_click_press")
DOOR_EVENTS = ("unlock", "door_open")


class History:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(SCHEMA)
        self._lock = threading.Lock()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _write(self, sql: str, rows: list[tuple]) -> None:
        with self._lock:
            self._db.executemany(sql, rows)
            self._db.commit()

    def _read(self, sql: str, args: tuple = ()) -> list[tuple]:
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    def import_events(self, entries: list[dict]) -> None:
        """One-time import of the old JSON log; skipped once the table has anything in it."""
        if entries and not self._read("SELECT 1 FROM events LIMIT 1"):
            self._write("INSERT INTO events (ts, device, event) VALUES (?, ?, ?)",
                        [(e["ts"], e["device"], e["event"]) for e in entries])

    def add_event(self, ts: float, device: str, event: str) -> None:
        self._write("INSERT INTO events (ts, device, event) VALUES (?, ?, ?)", [(ts, device, event)])

    def add_power(self, ts: float, device: str, is_on: bool) -> None:
        self._write("INSERT INTO power (ts, device, is_on) VALUES (?, ?, ?)", [(ts, device, int(is_on))])

    def events(self, before: float | None = None, limit: int = 100) -> dict:
        rows = self._read("SELECT ts, device, event FROM events WHERE ts < ? ORDER BY ts DESC LIMIT ?",
                          (before if before is not None else float("inf"), limit))
        total = self._read("SELECT COUNT(*) FROM events")[0][0]
        return {"total": total, "items": [{"ts": ts, "device": d, "event": e} for ts, d, e in rows]}

    def stats(self, days: int | None, tz_offset_min: int, kinds: dict[str, str]) -> dict:
        """Usage summary for the last `days` days (all time when None).

        tz_offset_min follows JavaScript's getTimezoneOffset(): minutes to add to local time to get UTC.
        kinds maps device id to its kind, so presses can be told from lock events.
        """
        now = time.time()
        first = self._read("SELECT MIN(ts) FROM (SELECT ts FROM events UNION ALL SELECT ts FROM power)")[0][0]
        since = now - days * 86400 if days else (first or now)
        local = lambda ts: ts - tz_offset_min * 60  # noqa: E731
        day_of = lambda ts: int(local(ts) // 86400)  # noqa: E731

        events = self._read("SELECT ts, device, event FROM events WHERE ts >= ? ORDER BY ts", (since,))
        powers = self._read("SELECT ts, device, is_on FROM power WHERE ts >= ? ORDER BY ts", (since,))

        presses = [(ts, d, e) for ts, d, e in events if kinds.get(d) == "switch" and e in PRESS_EVENTS]
        doors = [(ts, d, e) for ts, d, e in events if e in DOOR_EVENTS]
        turn_ons = []

        # Usage time: replay each device's transitions, starting from its state when the range began.
        on_seconds: dict[str, float] = defaultdict(float)
        on_count: Counter = Counter()
        state: dict[str, tuple[bool, float]] = {}
        for device, is_on in self._read(
                "SELECT device, is_on FROM power p WHERE ts = (SELECT MAX(ts) FROM power WHERE device = p.device AND ts < ?)",
                (since,)):
            state[device] = (bool(is_on), since)
        for ts, device, is_on in powers:
            was_on, start = state.get(device, (False, ts))
            if was_on and not is_on:
                on_seconds[device] += ts - start
                state[device] = (False, ts)
            elif is_on and not was_on:
                on_count[device] += 1
                turn_ons.append((ts, device))
                state[device] = (True, ts)
        for device, (is_on, start) in state.items():
            if is_on:
                on_seconds[device] += now - start

        span = max(now - since, 1)
        usage = sorted(
            ({"device": d, "on_seconds": round(on_seconds[d]), "turn_ons": on_count[d], "rate": on_seconds[d] / span}
             for d in set(on_seconds) | set(on_count)),
            key=lambda u: (-u["on_seconds"], -u["turn_ons"]))

        # Activity = things people did: presses, turning devices on, opening the door.
        activity = [ts for ts, _, _ in presses] + [ts for ts, _ in turn_ons] + [ts for ts, _, _ in doors]
        heat = [[0] * 24 for _ in range(7)]
        for ts in activity:
            t = local(ts)
            heat[int((t // 86400 + 3) % 7)][int(t % 86400 // 3600)] += 1  # 1970-01-01 was a Thursday; 0 = Monday

        first_day, last_day = day_of(since), day_of(now)
        daily = {d: {"presses": 0, "turn_ons": 0, "doors": 0} for d in range(max(first_day, last_day - 89), last_day + 1)}
        for key, items in (("presses", presses), ("doors", doors)):
            for ts, _, _ in items:
                if day_of(ts) in daily:
                    daily[day_of(ts)][key] += 1
        for ts, _ in turn_ons:
            if day_of(ts) in daily:
                daily[day_of(ts)]["turn_ons"] += 1

        hours = [sum(heat[w][h] for w in range(7)) for h in range(24)]
        return {
            "since": since,
            "first": first,
            "days": max(1, round(span / 86400)),
            "total_presses": len(presses),
            "press_types": dict(Counter(e for _, _, e in presses)),
            "total_turn_ons": len(turn_ons),
            "total_doors": len(doors),
            "switches": [{"device": d, "count": c} for d, c in Counter(d for _, d, _ in presses).most_common()],
            "usage": usage,
            "heatmap": heat,
            "peak_hour": max(range(24), key=lambda h: hours[h]) if activity else None,
            "daily": [{"day": d * 86400 + tz_offset_min * 60, **v} for d, v in daily.items()],
        }
