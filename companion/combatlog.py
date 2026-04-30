"""Parser for WoW Classic Era combat-log lines.

Combat-log format (one event per line):

    M/D HH:MM:SS.mmm  EVENT_NAME,sourceGUID,"sourceName",sourceFlags,sourceRaidFlags,
                       destGUID,"destName",destFlags,destRaidFlags, <event-specific args...>

We don't try to parse every event — just the ones that drive the stream UI:
SWING_DAMAGE, SPELL_DAMAGE, RANGE_DAMAGE, SPELL_PERIODIC_DAMAGE, SPELL_HEAL,
SPELL_PERIODIC_HEAL, SPELL_CAST_SUCCESS, UNIT_DIED, ENVIRONMENTAL_DAMAGE.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any

# Header is "M/D HH:MM:SS.mmm  EVENT,..."
LINE_RE = re.compile(r"^\s*(\d+/\d+)\s+(\d+:\d+:\d+\.\d+)\s{2,}(\S.*)$")

INTERESTING = {
    "SWING_DAMAGE",
    "SPELL_DAMAGE",
    "RANGE_DAMAGE",
    "SPELL_PERIODIC_DAMAGE",
    "SPELL_HEAL",
    "SPELL_PERIODIC_HEAL",
    "SPELL_CAST_SUCCESS",
    "UNIT_DIED",
    "ENVIRONMENTAL_DAMAGE",
}


def _split_csv(payload: str) -> list[str]:
    # Combat-log uses CSV with double-quoted strings and may contain commas in names.
    return next(csv.reader(io.StringIO(payload), skipinitialspace=False))


def parse(line: str) -> dict[str, Any] | None:
    """Parse one combat-log line. Return a typed event dict, or None."""
    m = LINE_RE.match(line)
    if not m:
        return None
    _date, ts, payload = m.group(1), m.group(2), m.group(3)
    try:
        fields = _split_csv(payload)
    except Exception:
        return None
    if not fields:
        return None
    event = fields[0]
    if event not in INTERESTING:
        return None

    # Common prefix: event,srcGUID,srcName,srcFlags,srcRaidFlags,dstGUID,dstName,dstFlags,dstRaidFlags
    if len(fields) < 9:
        return None
    base = {
        "t": "combat",
        "ts": ts,
        "event": event,
        "src": fields[2].strip('"') or None,
        "dst": fields[6].strip('"') or None,
    }

    args = fields[9:]
    # Per-event arg layout (Classic Era):
    if event == "SWING_DAMAGE":
        # args: amount, overkill, school, resisted, blocked, absorbed, critical, glancing, crushing
        if args:
            base["amount"] = _to_int(args[0])
            base["critical"] = bool(args[6]) if len(args) > 6 else False
        base["spell"] = "Melee"
    elif event in ("SPELL_DAMAGE", "RANGE_DAMAGE", "SPELL_PERIODIC_DAMAGE"):
        # args: spellId, "spellName", spellSchool, amount, overkill, school, ...
        if len(args) >= 4:
            base["spell"] = args[1].strip('"')
            base["amount"] = _to_int(args[3])
            base["critical"] = bool(args[9]) if len(args) > 9 else False
    elif event in ("SPELL_HEAL", "SPELL_PERIODIC_HEAL"):
        # args: spellId, "spellName", spellSchool, amount, overhealing, absorbed, critical
        if len(args) >= 4:
            base["spell"] = args[1].strip('"')
            base["amount"] = _to_int(args[3])
            base["heal"] = True
    elif event == "SPELL_CAST_SUCCESS":
        if len(args) >= 2:
            base["spell"] = args[1].strip('"')
    elif event == "UNIT_DIED":
        # No additional args of interest. dst is who died.
        pass
    elif event == "ENVIRONMENTAL_DAMAGE":
        # args: environmentalType, amount, ...
        if len(args) >= 2:
            base["spell"] = args[0].strip('"')
            base["amount"] = _to_int(args[1])

    return base


def _to_int(v: str) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0
