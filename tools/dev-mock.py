"""dev-mock.py — Simulate the ASCIIMUD addon without WoW running.

Writes ``ASCIIMUD|{json}`` lines to a file just like the in-game addon does
via /chatlog, so you can develop and test the companion + overlay without WoW.

Usage:
    python tools/dev-mock.py                        # writes to a temp file, prints path
    python tools/dev-mock.py --out path/to/log.txt  # append to a specific file
    python tools/dev-mock.py --scenario death       # specific scenario
    python tools/dev-mock.py --hz 4                 # 4 events/sec

Scenarios:
    wander   (default) normal exploration, mild combat
    boss     high-severity sustained combat
    death    character dies
    levelup  character levels up

The companion's config.toml log_path should point at the file this script writes.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import tempfile
import time
from pathlib import Path

PREFIX = "ASCIIMUD~"
PLAYER = {"name": "Testwick", "class": "WARLOCK", "level": 12,
          "hp": 320, "hpMax": 360, "mp": 180, "mpMax": 200}
ZONE   = {"name": "Elwynn Forest", "subzone": "Goldshire", "x": 0, "y": 0}

ZONES = [
    {"name": "Elwynn Forest",    "subzone": "Goldshire"},
    {"name": "Westfall",         "subzone": "Sentinel Hill"},
    {"name": "Redridge Mountains","subzone": "Lakeshire"},
]
MOBS  = ["Defias Thug", "Gnoll Brute", "Goretusk Boar", "Defias Bandit"]


def emit(f, obj: dict) -> None:
    line = PREFIX + json.dumps(obj, separators=(",", ":")) + "\n"
    f.write(line)
    f.flush()


def snapshot(tick: int, player: dict, zone: dict,
             target: dict | None, combat: bool, sev: int) -> dict:
    return {
        "t": "snapshot",
        "data": {
            "v": 1,
            "tick": tick,
            "combat": combat,
            "chapter": 1,
            "player": player,
            "zone": zone,
            "target": target,
        },
    }


def run_wander(f, hz: float) -> None:
    """Normal exploration then a short fight."""
    p = dict(PLAYER)
    z = dict(ZONES[0])
    target = None
    combat = False
    sev = 0
    tick = 0

    print("[mock] scenario: wander — exploring then fighting", flush=True)
    for i in range(200):
        tick += 1
        delay = 1.0 / hz

        if i == 20:
            z = dict(random.choice(ZONES))
            emit(f, {"t": "zone", "zone": z})
        if i == 40:
            target = {"name": random.choice(MOBS), "level": p["level"] - 1,
                      "hp": 120, "hpMax": 120, "hostile": True}
            combat = True
            sev = 2
            emit(f, {"t": "severity", "level": sev})
        if 40 <= i <= 70:
            pct = (70 - i) / 30.0
            p["hp"] = max(1, int(p["hpMax"] * pct))
            p["mp"] = max(0, int(p["mpMax"] * pct))
            sev = min(5, 2 + int((1 - pct) * 3))
            if target:
                target["hp"] = max(0, int(target["hpMax"] * pct))
            if i == 70:
                target = None; combat = False; sev = 0
                emit(f, {"t": "severity", "level": 0})
                p["hp"] = p["hpMax"]; p["mp"] = p["mpMax"]
        if i % 3 == 0:
            emit(f, snapshot(tick, p, z, target, combat, sev))
            emit(f, {"t": "severity", "level": sev})
        print(f"  tick {tick:03d}  hp={p['hp']}/{p['hpMax']}  sev={sev}", flush=True)
        time.sleep(delay)


def run_death(f, hz: float) -> None:
    """HP drains to zero, death event."""
    p = dict(PLAYER)
    z = dict(ZONES[0])
    target = {"name": "Elite Cultist", "level": 15, "hp": 800, "hpMax": 800, "hostile": True}
    print("[mock] scenario: death", flush=True)
    for i in range(60):
        pct = max(0, 1 - i / 50.0)
        p["hp"] = int(p["hpMax"] * pct)
        sev = min(5, int((1 - pct) * 6))
        emit(f, snapshot(i, p, z, target, True, sev))
        emit(f, {"t": "severity", "level": sev})
        if pct == 0 and i == 50:
            emit(f, {"t": "death", "player": p["name"]})
            print("  ** DEATH EVENT EMITTED **", flush=True)
        print(f"  tick {i:03d}  hp={p['hp']}/{p['hpMax']}  sev={sev}", flush=True)
        time.sleep(1.0 / hz)


def run_boss(f, hz: float) -> None:
    """Sustained high-severity boss fight with wave severity."""
    p = dict(PLAYER)
    z = {"name": "The Deadmines", "subzone": "Deadmines Instance"}
    target = {"name": "Edwin VanCleef", "level": 20, "hp": 5000, "hpMax": 5000, "hostile": True}
    print("[mock] scenario: boss", flush=True)
    for i in range(120):
        pct = 0.3 + 0.2 * math.sin(i * 0.2)
        p["hp"] = max(1, int(p["hpMax"] * pct))
        t_pct = max(0, 1 - i / 100.0)
        target["hp"] = int(target["hpMax"] * t_pct)
        sev = min(5, 3 + int(math.sin(i * 0.3) * 2))
        emit(f, snapshot(i, p, z, target, True, sev))
        emit(f, {"t": "severity", "level": sev})
        print(f"  tick {i:03d}  hp={p['hp']}/{p['hpMax']}  sev={sev}", flush=True)
        time.sleep(1.0 / hz)


def run_levelup(f, hz: float) -> None:
    """Character levels up mid-exploration."""
    p = dict(PLAYER)
    z = dict(ZONES[1])
    print("[mock] scenario: levelup", flush=True)
    for i in range(40):
        if i == 20:
            p["level"] += 1
            p["hpMax"] = int(p["hpMax"] * 1.1)
            p["hp"] = p["hpMax"]
            p["mpMax"] = int(p["mpMax"] * 1.1)
            p["mp"] = p["mpMax"]
            print(f"  ** LEVEL UP -> {p['level']} **", flush=True)
        emit(f, snapshot(i, p, z, None, False, 0))
        emit(f, {"t": "severity", "level": 0})
        print(f"  tick {i:03d}  level={p['level']}", flush=True)
        time.sleep(1.0 / hz)


SCENARIOS = {"wander": run_wander, "death": run_death,
             "boss": run_boss, "levelup": run_levelup}


def main() -> None:
    ap = argparse.ArgumentParser(description="ASCIIMUD addon mock")
    ap.add_argument("--out", default="", help="output file path (default: temp file)")
    ap.add_argument("--scenario", choices=list(SCENARIOS), default="wander")
    ap.add_argument("--hz", type=float, default=2.0, help="events per second")
    args = ap.parse_args()

    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        f = path.open("a", encoding="utf-8")
        print(f"[mock] writing to {path}", flush=True)
    else:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", prefix="WoWChatLog_mock_",
            encoding="utf-8", delete=False
        )
        f = tmp
        print(f"[mock] temp log: {tmp.name}", flush=True)
        print(f"[mock] point companion config.toml -> log_path = \"{tmp.name}\"", flush=True)

    print(f"[mock] scenario={args.scenario}  hz={args.hz}", flush=True)
    print("[mock] Ctrl-C to stop\n", flush=True)
    try:
        SCENARIOS[args.scenario](f, args.hz)
    except KeyboardInterrupt:
        print("\n[mock] stopped.", flush=True)
    finally:
        f.close()


if __name__ == "__main__":
    main()
