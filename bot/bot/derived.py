"""Snapshot delta engine.

Consumes the raw `t`-tagged events the companion broadcasts. Emits synthesized
events the bot needs (level_up, close_call, etc.) and maintains run counters.

Pure, no I/O. The caller pumps `feed(evt)` and consumes the returned list of
`(kind, facts)` tuples.
"""
from __future__ import annotations

import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Deque

from .narration import danger_label
from .zones import name as zone_name

LOG = logging.getLogger("asciimud.bot.derived")

CLOSE_CALL_HP = 25
CLOSE_CALL_RECOVER_HP = 50
ADDON_STALE_SECONDS = 12.0


@dataclass
class Counters:
    kill_count: int = 0
    close_call_count: int = 0
    death_count: int = 0
    run_started_at: float = field(default_factory=time.time)
    last_death_at: float | None = None

    def time_alive(self) -> float:
        anchor = self.last_death_at or self.run_started_at
        return max(0.0, time.time() - anchor)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kill_count": self.kill_count,
            "close_call_count": self.close_call_count,
            "death_count": self.death_count,
            "run_started_at": self.run_started_at,
            "last_death_at": self.last_death_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Counters":
        return cls(
            kill_count=int(d.get("kill_count", 0)),
            close_call_count=int(d.get("close_call_count", 0)),
            death_count=int(d.get("death_count", 0)),
            run_started_at=float(d.get("run_started_at", time.time())),
            last_death_at=(float(d["last_death_at"])
                           if d.get("last_death_at") is not None else None),
        )

    def save(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.to_dict(), indent=2),
                           encoding="utf-8")
            tmp.replace(path)
        except OSError as e:
            LOG.warning("counters save failed: %s", e)

    @classmethod
    def load(cls, path: Path) -> "Counters":
        try:
            return cls.from_dict(
                json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return cls()


class Derived:
    def __init__(self, broadcaster_display: str, recap_ring_size: int = 12,
                 counters: Counters | None = None) -> None:
        self.broadcaster_display = broadcaster_display
        self.counters = counters or Counters()
        self.recap: Deque[str] = deque(maxlen=recap_ring_size)
        self.objective: str | None = None
        self.objective_changed_at: float | None = None

        # Last-snapshot fields used for diffs.
        self._last_level: int | None = None
        self._last_in_combat: bool | None = None
        self._last_zone_hash: int | None = None
        self._last_target: str | None = None
        self._last_target_lvl: int | None = None
        self._last_severity: int = 0
        self._last_danger: str = "none"
        self._last_hp_pct: int = 100
        self._last_class: str | None = None

        # Close-call latch + cooldown.
        self._close_call_armed: bool = False
        self._close_call_low: int = 100
        self._last_close_call_at: float = 0.0
        self._last_death_signal_at: float = 0.0

        self._last_snapshot_at: float = 0.0
        self._addon_disconnected: bool = False

    # ----------------- counter persistence helpers ---------------------------
    def reset_run(self) -> None:
        self.counters = Counters()

    # ----------------- public API --------------------------------------------
    def feed(self, evt: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        t = evt.get("t")
        if t == "snapshot":
            return self._on_snapshot(evt.get("data") or {})
        if t == "severity":
            return self._on_severity(int(evt.get("level", 0)))
        if t == "death":
            return self._on_death_event(evt)
        if t == "combat":
            return self._on_combat(evt)
        if t == "engaged_target":
            n = evt.get("name") or None
            if n and n != self._last_target:
                self._last_target = n
                return [("target_changed", self._facts(targetName=n))]
        return []

    def tick(self, now: float | None = None) -> list[tuple[str, dict[str, Any]]]:
        """Time-driven checks: addon disconnect detection."""
        n = time.monotonic() if now is None else now
        if self._last_snapshot_at == 0.0:
            return []
        out: list[tuple[str, dict[str, Any]]] = []
        stale = (n - self._last_snapshot_at) > ADDON_STALE_SECONDS
        if stale and not self._addon_disconnected:
            self._addon_disconnected = True
            out.append(("addon_disconnected", self._facts()))
        return out

    def on_ws_closed(self) -> list[tuple[str, dict[str, Any]]]:
        if self._addon_disconnected:
            return []
        self._addon_disconnected = True
        return [("addon_disconnected", self._facts())]

    def on_ws_open(self) -> list[tuple[str, dict[str, Any]]]:
        if self._addon_disconnected:
            self._addon_disconnected = False
            return [("addon_reconnected", self._facts())]
        return []

    def set_objective(self, text: str) -> tuple[str, dict[str, Any]]:
        self.objective = text.strip() or None
        self.objective_changed_at = time.time()
        return ("objective_changed", self._facts(objective=self.objective))

    # ----------------- internals --------------------------------------------
    def _on_snapshot(self, data: dict) -> list[tuple[str, dict[str, Any]]]:
        out: list[tuple[str, dict[str, Any]]] = []
        was_disc = self._addon_disconnected
        self._last_snapshot_at = time.monotonic()
        if was_disc:
            self._addon_disconnected = False
            out.append(("addon_reconnected", self._facts()))

        p = data.get("player") or {}
        z = data.get("zone") or {}
        tgt = data.get("target") or {}
        in_combat = bool(data.get("combat"))
        hp_pct = int(p.get("hpPct", self._last_hp_pct))
        level = int(p.get("level") or 0)
        cls = p.get("class") or self._last_class
        self._last_class = cls
        zone_h = z.get("hash")
        target_name = tgt.get("name") if isinstance(tgt, dict) else None
        target_lvl = tgt.get("level") if isinstance(tgt, dict) else None

        # Level up
        if (self._last_level is not None
                and level and level > self._last_level):
            out.append(("level_up", self._facts(
                level=level, class_=cls,
                zoneHash=zone_h)))
            self.recap.append(f"Level up to {level}")

        # Combat enter/leave
        if self._last_in_combat is not None and in_combat != self._last_in_combat:
            kind = "entered_combat" if in_combat else "left_combat"
            out.append((kind, self._facts(
                inCombat=in_combat, hpPct=hp_pct,
                targetName=target_name, targetLevel=target_lvl)))
            self.recap.append("Engaged combat" if in_combat else "Left combat")

        # Target changed
        if target_name != self._last_target:
            out.append(("target_changed", self._facts(
                targetName=target_name, targetLevel=target_lvl)))

        # Zone changed
        if (self._last_zone_hash is not None
                and zone_h is not None and zone_h != self._last_zone_hash):
            out.append(("zone_changed", self._facts(zoneHash=zone_h)))
            self.recap.append(f"Entered {zone_name(zone_h)}")

        # Close call: arm at low HP, fire on recovery, then re-arm.
        if hp_pct <= CLOSE_CALL_HP:
            self._close_call_armed = True
            if hp_pct < self._close_call_low:
                self._close_call_low = hp_pct
        elif self._close_call_armed and hp_pct >= CLOSE_CALL_RECOVER_HP:
            now = time.monotonic()
            if (now - self._last_close_call_at) >= 30:
                self._last_close_call_at = now
                self.counters.close_call_count += 1
                low = self._close_call_low
                self.recap.append(f"Close call at HP {low}%")
                out.append(("close_call", self._facts(
                    lowestHpPct=low, hpPct=hp_pct)))
            self._close_call_armed = False
            self._close_call_low = 100

        # Snapshot-driven death detection (fallback for unreliable chat-log).
        if hp_pct == 0 and self._last_in_combat and not in_combat:
            out.append(self._record_death(level=level))

        # Danger level edge
        new_danger = danger_label(self._last_severity, hp_pct, in_combat)
        if new_danger != self._last_danger:
            out.append(("danger_changed", self._facts(
                dangerLevel=new_danger, hpPct=hp_pct, inCombat=in_combat,
                targetName=target_name, targetLevel=target_lvl,
                dangerReasons=self._danger_reasons(new_danger, hp_pct, in_combat))))
            self._last_danger = new_danger

        # Always emit a state_update (caller decides whether to post).
        out.append(("state_update", self._facts(
            level=level, class_=cls, hpPct=hp_pct, zoneHash=zone_h,
            inCombat=in_combat, targetName=target_name,
            targetLevel=target_lvl, dangerLevel=new_danger)))

        self._last_level = level or self._last_level
        self._last_in_combat = in_combat
        self._last_zone_hash = zone_h if zone_h is not None else self._last_zone_hash
        self._last_target = target_name
        self._last_target_lvl = target_lvl
        self._last_hp_pct = hp_pct
        return out

    def _on_severity(self, level: int) -> list[tuple[str, dict[str, Any]]]:
        self._last_severity = level
        new_danger = danger_label(level, self._last_hp_pct, bool(self._last_in_combat))
        if new_danger == self._last_danger:
            return []
        self._last_danger = new_danger
        return [("danger_changed", self._facts(
            dangerLevel=new_danger, hpPct=self._last_hp_pct,
            inCombat=self._last_in_combat,
            dangerReasons=self._danger_reasons(
                new_danger, self._last_hp_pct, bool(self._last_in_combat))))]

    def _on_combat(self, evt: dict) -> list[tuple[str, dict[str, Any]]]:
        if evt.get("event") != "UNIT_DIED":
            return []
        # A monster died (dst != broadcaster). Treat as a kill if dst is
        # someone other than us — heuristic since we don't know GUIDs.
        dst = evt.get("dst") or ""
        if dst and dst != self.broadcaster_display:
            self.counters.kill_count += 1
            self.recap.append(f"Killed {dst}")
            return []
        # If WE died via combatlog UNIT_DIED.
        if dst and dst == self.broadcaster_display:
            return [self._record_death()]
        return []

    def _on_death_event(self, evt: dict) -> list[tuple[str, dict[str, Any]]]:
        return [self._record_death()]

    def _record_death(self, level: int | None = None) -> tuple[str, dict[str, Any]]:
        now = time.monotonic()
        if (now - self._last_death_signal_at) < 5:
            return ("state_update", self._facts())  # de-duplicated
        self._last_death_signal_at = now
        self.counters.death_count += 1
        self.counters.last_death_at = time.time()
        self.recap.append("Death recorded")
        return ("death", self._facts(level=level or self._last_level))

    def _danger_reasons(self, danger: str, hp_pct: int, in_combat: bool) -> list[str]:
        r: list[str] = []
        if hp_pct <= 30:
            r.append(f"HP {hp_pct}%")
        if in_combat:
            r.append("in combat")
        if self._last_target_lvl and self._last_level:
            diff = self._last_target_lvl - self._last_level
            if diff >= 2:
                r.append(f"target {diff} levels above player")
        return r

    # ----------------- fact assembly ----------------------------------------
    def _facts(self, **overrides: Any) -> dict[str, Any]:
        f = {
            "playerName": self.broadcaster_display or None,
            "level": self._last_level,
            "class": self._last_class,
            "hpPct": self._last_hp_pct,
            "zoneHash": self._last_zone_hash,
            "inCombat": bool(self._last_in_combat),
            "targetName": self._last_target,
            "targetLevel": self._last_target_lvl,
            "dangerLevel": self._last_danger,
            "lastEvent": (self.recap[-1] if self.recap else "—"),
            "objective": self.objective,
            "objectiveChangedAgo": (
                time.time() - self.objective_changed_at
                if self.objective_changed_at else None),
            "killCount": self.counters.kill_count,
            "closeCallCount": self.counters.close_call_count,
            "deathCount": self.counters.death_count,
            "timeAlive": self.counters.time_alive(),
        }
        f.update({k.rstrip("_"): v for k, v in overrides.items()})
        return f

    def snapshot_facts(self) -> dict[str, Any]:
        """Public fact bundle for command handlers."""
        return self._facts()

    def recap_facts(self, max_items: int = 5) -> dict[str, Any]:
        events = list(self.recap)[-max_items:]
        return self._facts(events=events, max=max_items)
