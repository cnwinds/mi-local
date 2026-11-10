"""MIoT specs from miot-spec.org, cached on disk and turned into display fields with Chinese labels.

A field: {key "siid.piid", siid, piid, service, svc, name, prop, format, unit, range, values, writable}.
`service`/`name` are display labels; `svc`/`prop` are the urn names ("light", "brightness") code can rely on.
"""
import json
import logging
import re
import time

import requests

from .store import DATA_DIR

log = logging.getLogger(__name__)

HOST = "https://miot-spec.org"
CACHE_DIR = DATA_DIR / "specs"
INSTANCES_MAX_AGE = 7 * 86400
# A model missing from an index younger than this has no spec; don't download the index again for it.
INSTANCES_RETRY = 3600
SKIP_SERVICES = {"device-information"}
SKIP_PROPS = {"audio-id"}
TEMPERATURE_PROPS = {"temperature", "target-temperature"}

# Fallbacks for specs that ship without a zh_cn translation, keyed by the urn name.
SERVICE_ZH = {
    "water-heater": "热水器", "hood": "油烟机", "fan-control": "风机", "light": "灯", "environment": "环境",
    "speaker": "扬声器", "microphone": "麦克风", "intelligent-speaker": "智能音箱", "play-control": "播放",
    "clock": "闹钟", "no-disturb": "免打扰", "filter": "滤芯", "alarm": "提示音", "indicator-light": "指示灯",
    "physical-controls-locked": "童锁", "air-purifier": "空气净化器", "fan": "风扇", "dehumidifier": "除湿机",
    "induction-cooker": "电磁炉", "toilet": "马桶盖", "microwave-oven": "微波炉", "water-purifier": "净水器",
}
PROP_ZH = {
    "on": "开关", "mode": "模式", "fan-level": "风量", "target-temperature": "目标温度", "temperature": "当前温度",
    "heat-level": "火力", "working-time": "已工作", "filter-used-time": "滤芯已用时间", "filter-used-flow": "滤芯已用水量",
    "off-delay-time": "定时关机", "tds-in": "入水 TDS", "tds-out": "出水 TDS", "countdown-time": "倒计时",
    "status": "状态", "fault": "故障", "brightness": "亮度", "color-temperature": "色温", "volume": "音量",
    "mute": "静音", "pm2.5-density": "PM2.5", "relative-humidity": "湿度", "target-humidity": "目标湿度",
    "filter-life-level": "滤芯剩余", "filter-left-time": "滤芯剩余时间", "left-time": "剩余时间",
    "physical-controls-locked": "童锁", "alarm": "提示音", "sleep-mode": "睡眠模式", "no-disturb": "免打扰",
    "enable-time-period": "生效时段", "playing-state": "播放状态", "play-loop-mode": "循环模式", "ringtone": "铃声",
}
VALUE_ZH = {
    "Off": "关闭", "On": "开启", "Idle": "空闲", "Busy": "工作中", "Low": "低档", "Medium": "中档", "Middle": "中档",
    "High": "高档", "Stir-fry": "爆炒", "Playing": "播放中", "Paused": "已暂停", "Auto": "自动", "Sleep": "睡眠",
    "No Faults": "无故障", "Single Cycle": "单曲循环", "Favorite": "喜爱", "Fault": "故障", "None": "无",
    "Day": "白天", "Night": "夜间", "Wear Immediately": "即穿", "Iron": "可熨烫", "Store": "收纳",
}
RENAME = {"物理控制锁": "童锁"}
CJK = re.compile(r"[\u4e00-\u9fff]")


def _clean(text: str | None) -> str:
    """Translations sometimes carry developer notes: '启用时间段(格式为：...)', '运行时长，累计720小时就重置'."""
    text = re.split(r"[(（，,]", (text or "").strip())[0].strip()
    return RENAME.get(text, text)


def _zh(translated: str | None, fallbacks: dict[str, str], key: str, default: str | None) -> str | None:
    """Prefer the official translation unless it is just English again."""
    t = _clean(translated)
    if t and CJK.search(t):
        return t
    return fallbacks.get(key) or t or default


def _get(path: str, **params) -> dict:
    resp = requests.get(HOST + path, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _instances(wanted: list[str]) -> dict[str, str]:
    """model -> spec urn. Refetches the index (several MB) only when it is stale or lacks a wanted model."""
    cache = CACHE_DIR / "_instances.json"
    urns, age = None, float("inf")
    if cache.exists():
        age = time.time() - cache.stat().st_mtime
        urns = json.loads(cache.read_text(encoding="utf-8"))
    missing = urns is None or any(m not in urns for m in wanted)
    if age > INSTANCES_MAX_AGE or (missing and age > INSTANCES_RETRY):
        try:
            latest: dict[str, tuple[str, int]] = {}
            for i in _get("/miot-spec-v2/instances", status="all")["instances"]:
                if i["model"] not in latest or i["version"] > latest[i["model"]][1]:
                    latest[i["model"]] = (i["type"], i["version"])
            urns = {m: t for m, (t, _) in latest.items()}
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(urns), encoding="utf-8")
        except Exception:
            if urns is None:
                raise
            log.debug("spec index refresh failed, using the cached one", exc_info=True)
    return urns or {}


def _urn_for(model: str) -> str | None:
    return _instances([model]).get(model)


def device_types(models: list[str]) -> dict[str, str]:
    """Spec device type per model ("light", "air-conditioner", "curtain"…); models without a spec are left out."""
    urns = _instances(models)
    return {m: _name(urns[m]) for m in models if m in urns}


def _name(urn: str) -> str:
    return urn.split(":")[3]


def parse(spec: dict, zh: dict[str, str]) -> list[dict]:
    fields = []
    for s in spec.get("services", []):
        if _name(s["type"]) in SKIP_SERVICES:
            continue
        sk = f"service:{s['iid']:03}"
        service = _zh(zh.get(sk), SERVICE_ZH, _name(s["type"]), s.get("description") or _name(s["type"]))
        for p in s.get("properties", []):
            if "read" not in p.get("access", []) or _name(p["type"]) in SKIP_PROPS:
                continue
            pk = f"{sk}:property:{p['iid']:03}"
            vendor = p["type"].split(":")[1] != "miot-spec-v2"
            raw_label = zh.get(pk) or ""
            label = _zh(raw_label, PROP_ZH, _name(p["type"]), None)
            values = [{"value": v["value"], "name": v["description"],
                       "label": _zh(zh.get(f"{pk}:valuelist:{i:03}"), VALUE_ZH, v["description"], v["description"])}
                      for i, v in enumerate(p.get("value-list", []))]
            if "位图" in raw_label:
                continue
            # Vendor extensions are often raw blobs or bitmasks; keep only the ones that read as plain values.
            if vendor and (not label or p["format"] == "string" or (p["format"] in ("uint32", "int32") and not values)):
                continue
            unit = p.get("unit")
            if unit in (None, "none") and _name(p["type"]) in TEMPERATURE_PROPS:
                unit = "celsius"
            fields.append({
                "key": f"{s['iid']}.{p['iid']}", "siid": s["iid"], "piid": p["iid"],
                "service": service, "svc": _name(s["type"]), "name": label or p.get("description") or _name(p["type"]),
                "prop": _name(p["type"]), "format": p["format"],
                "unit": None if unit in (None, "none") else unit,
                "range": p.get("value-range"), "values": values, "writable": "write" in p.get("access", []),
                "vendor": vendor,
            })
    return fields


def load_fields(model: str) -> list[dict] | None:
    """Fields for a model, from the disk cache or miot-spec.org. None if the model has no spec."""
    cache = CACHE_DIR / f"{model}.json"
    cached = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    if "spec" not in cached:
        urn = _urn_for(model)
        if not urn:
            return None
        spec = _get("/miot-spec-v2/instance", type=urn)
        try:
            zh = _get("/instance/v2/multiLanguage", urn=urn).get("data", {}).get("zh_cn", {})
        except Exception as e:
            log.debug("no translation for %s: %s", model, e)
            zh = {}
        cached = {"urn": urn, "spec": spec, "zh": zh}
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(cached, ensure_ascii=False), encoding="utf-8")
    return parse(cached["spec"], cached["zh"])
