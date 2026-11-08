"""Rule engine: device event -> actions.

A rule looks like:
{
  "id": "r1", "name": "...", "enabled": true,
  "trigger": {"type": "device_event", "device": "lumi.158d...", "event": "click"},
  "actions": [{"device": "100000002", "action": "toggle"}]
}
Several "toggle" actions in one rule act as a group: if any target is on, all turn off;
otherwise all turn on. This keeps a multi-light switch from leaving lights out of sync.
"""
import asyncio
import logging

log = logging.getLogger(__name__)


def matches(rule: dict, device_id: str, event: str) -> bool:
    trig = rule.get("trigger", {})
    return (
        rule.get("enabled", True)
        and trig.get("type") == "device_event"
        and trig.get("device") == device_id
        and trig.get("event") == event
    )


def resolve_toggles(actions: list[dict], powered: dict[str, bool]) -> list[dict]:
    toggles = [a for a in actions if a["action"] == "toggle"]
    if not toggles:
        return actions
    target = "turn_off" if any(powered.get(a["device"]) for a in toggles) else "turn_on"
    return [{**a, "action": target} if a["action"] == "toggle" else a for a in actions]


class RuleEngine:
    def __init__(self, hub):
        self.hub = hub

    def handle_event(self, device_id: str, event: str) -> None:
        for rule in self.hub.rules:
            if matches(rule, device_id, event):
                asyncio.create_task(self.run(rule))

    async def run(self, rule: dict) -> None:
        actions = rule.get("actions", [])
        toggle_ids = {a["device"] for a in actions if a["action"] == "toggle"}
        states = await asyncio.gather(*(self.hub.refresh(d) for d in toggle_ids))
        powered = {d: s.get("power", False) for d, s in zip(toggle_ids, states)}
        resolved = resolve_toggles(actions, powered)
        results = await asyncio.gather(
            *(self.hub.command(a["device"], a["action"], a.get("value")) for a in resolved),
            return_exceptions=True,
        )
        for action, result in zip(resolved, results):
            if isinstance(result, Exception):
                log.warning("rule %s action %s failed: %s", rule.get("name"), action, result)
        log.info("rule %s ran: %s", rule.get("name"), resolved)
