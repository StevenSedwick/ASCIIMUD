"""Tone helpers and small formatters."""
from __future__ import annotations

DANGER_LABELS = {
    0: "none",
    1: "low",
    2: "low",
    3: "medium",
    4: "HIGH",
    5: "CRITICAL",
}


def danger_label(severity: int | None, hp_pct: int | None, in_combat: bool) -> str:
    """Combine raw severity with HP/combat to produce a stable bucket."""
    sev = int(severity or 0)
    hp = int(hp_pct if hp_pct is not None else 100)
    if hp <= 15:
        return "CRITICAL"
    if hp <= 30 and in_combat:
        return "HIGH"
    return DANGER_LABELS.get(sev, "low")


def fmt_secs(s: float) -> str:
    s = int(max(0, s))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{sec:02d}s"
    return f"{sec}s"


def hp_phrase(hp_pct: int | None) -> str:
    if hp_pct is None:
        return "HP ?"
    return f"HP {int(hp_pct)}%"
