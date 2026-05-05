"""Rule engine.

Maps synthesized events from `derived.Derived` to (cooldown_key,
cooldown_seconds, event_kind) tuples. Returns a `(should_post, kind, facts,
key, interval)` decision; the caller composes the message and sends it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import Cooldowns


@dataclass
class Decision:
    post: bool = False
    kind: str = ""
    facts: dict[str, Any] | None = None
    key: str = ""
    interval: float = 0.0


def decide(kind: str, facts: dict[str, Any], cd: Cooldowns) -> Decision:
    f = facts or {}

    # Always-post (subject only to global throttle + dedupe).
    if kind == "level_up":
        return Decision(True, kind, f, "level_up", 0)
    if kind == "objective_changed":
        return Decision(True, kind, f, "objective_changed", 0)
    if kind == "death":
        return Decision(True, kind, f, "death", 0)
    if kind == "addon_disconnected":
        return Decision(True, kind, f, "addon_disconnected", cd.addon_disconnect)
    if kind == "addon_reconnected":
        return Decision(True, kind, f, "addon_reconnected", cd.addon_disconnect)

    if kind == "danger_changed":
        d = f.get("dangerLevel")
        if d == "CRITICAL":
            return Decision(True, kind, f, "danger_critical", cd.danger_critical)
        if d == "HIGH":
            return Decision(True, kind, f, "danger_high", cd.danger_high)
        return Decision(False)

    if kind == "close_call":
        return Decision(True, kind, f, "close_call", cd.close_call)

    if kind == "stream_start":
        return Decision(True, kind, f, "stream_start", 1e12)  # once per process

    if kind == "recap_tick":
        return Decision(True, "recap", f, "recap", cd.recap)

    # Everything else is informational only.
    return Decision(False)
