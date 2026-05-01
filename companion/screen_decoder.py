"""Decode the ASCIIMUD ScreenGrid from a WoW screenshot.

Mirrors addon/stream/ScreenGrid.lua. Grid is 64 cols x 8 rows = 512 cells
= 64 bytes per tick. White cell = 1, black cell = 0.

Schema (see ScreenGrid.lua for full bit layout):
    byte 0       magic = 0xA5
    byte 1       tick % 256
    byte 2-3     hp           (u16 BE)
    byte 4-5     hpMax        (u16 BE)
    byte 6-7     mp           (u16 BE)
    byte 8-9     mpMax        (u16 BE)
    byte 10      level<<1 | resting
    byte 11      class<<4 | race
    byte 12      flags: combat/gender/faction/mounted/pvp/grouped/hasPet/-
    byte 13      xpPct<<1 | restedXP
    byte 14-15   zoneHash (u16 BE, polynomial hash)
    byte 16      mapX (0-255)
    byte 17      mapY (0-255)
    byte 18      facing (0-255 = 0..2pi)
    byte 19      durabilityPct<<1 | bagFull
    byte 20-22   gold pieces (u24 BE)
    byte 23      bagFreeSlots
    byte 24-25   target hp     (u16)
    byte 26-27   target hpMax  (u16)
    byte 28      tLevel<<1 | hasTarget
    byte 29      target flags: hostile/isPlayer/classification(3b)/-
    byte 30-31   target cast spell id (u16; 0 = none)
    byte 32      target cast progress %
    byte 33-34   player cast spell id (u16)
    byte 35      player cast progress %
    byte 36-43   buffs:   4 x u16 spell ids
    byte 44-51   debuffs: 4 x u16 spell ids
    byte 52-61   action bar cooldowns (10 x u8)
    byte 62      combo<<5 | powerType<<2 | reserved
    byte 63      checksum = sum(bytes 0..62) % 256
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError as e:  # pragma: no cover
    raise SystemExit("Install Pillow: pip install Pillow") from e

CELL_PX      = 12
GRID_COLS    = 64
GRID_ROWS    = 8
TOTAL_BYTES  = (GRID_COLS * GRID_ROWS) // 8     # 64
TOTAL_CELLS  = GRID_COLS * GRID_ROWS            # 512
SIZE_W       = CELL_PX * GRID_COLS              # 768 px
SIZE_H       = CELL_PX * GRID_ROWS              # 96 px
QUIET_PX     = 12                               # black border the addon adds
MAGIC        = 0xA5
LUMA_THRESH  = 128

CLASS_NAMES = {
    0: "?", 1: "Warrior", 2: "Paladin", 3: "Hunter", 4: "Rogue", 5: "Priest",
    7: "Shaman", 8: "Mage", 9: "Warlock", 11: "Druid",
}
RACE_NAMES = {
    0: "?", 1: "Human", 2: "Orc", 3: "Dwarf", 4: "Night Elf", 5: "Undead",
    6: "Tauren", 7: "Gnome", 8: "Troll",
}
CLASSIFICATIONS = ["normal", "elite", "rareelite", "rare",
                   "worldboss", "trivial", "minion", "?"]
POWER_TYPES = {0: "mana", 1: "rage", 2: "focus", 3: "energy",
               4: "happiness", 5: "runes", 6: "runic_power", 7: "?"}


def hash16(s: str) -> int:
    """Polynomial hash that matches the addon (Lua-double-safe)."""
    h = 0
    for c in s.encode("utf-8"):
        h = (h * 31 + c) % 65536
    return h


@dataclass
class Decoded:
    magic_ok: bool
    checksum_ok: bool
    tick: int
    hp: int
    hp_max: int
    mp: int
    mp_max: int
    level: int
    is_resting: bool
    class_id: int
    race_id: int
    in_combat: bool
    gender: int           # 0=male,1=female
    faction: int          # 0=ally,1=horde
    mounted: bool
    pvp_flagged: bool
    grouped: bool
    has_pet: bool
    xp_pct: int
    rested_xp: bool
    zone_hash: int
    map_x: int
    map_y: int
    facing: int           # 0-255
    durability_pct: int
    bag_full: bool
    gold: int             # gold pieces
    bag_free: int
    has_target: bool
    target_hp: int
    target_hp_max: int
    target_level: int
    target_hostile: bool
    target_is_player: bool
    target_classification: int
    target_cast_spell: int
    target_cast_progress: int
    player_cast_spell: int
    player_cast_progress: int
    buffs: list[int] = field(default_factory=list)
    debuffs: list[int] = field(default_factory=list)
    action_cooldowns: list[int] = field(default_factory=list)
    combo_points: int = 0
    power_type: int = 0
    raw_bytes: bytes = b""


def _luma(px) -> int:
    r, g, b = px[:3]
    return (r * 299 + g * 587 + b * 114) // 1000


def _find_grid_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    """Find the white cells in the bottom-right corner.
    Grid is 64x8 cells × 12px = 768x96, with a 12px black quiet zone, so
    we search the bottom-right ~830x130 region.
    """
    w, h = img.size
    search_w = min(SIZE_W + 2 * QUIET_PX + 40, w)
    search_h = min(SIZE_H + 2 * QUIET_PX + 40, h)
    x0 = w - search_w
    y0 = h - search_h
    px = img.load()

    right = top = bottom = -1
    left = w
    for y in range(y0, h):
        for x in range(x0, w):
            if _luma(px[x, y]) >= LUMA_THRESH:
                if x < left:
                    left = x
                if x > right:
                    right = x
                if top == -1 or y < top:
                    top = y
                if y > bottom:
                    bottom = y
    if right < 0 or top < 0:
        return None
    return left, top, right, bottom


def decode(path: Path) -> Decoded | None:
    with Image.open(path) as im:
        im = im.convert("RGB")
        bbox = _find_grid_bbox(im)
        if bbox is None:
            return None
        left, top, right, bottom = bbox
        cell_w = (right - left + 1) / GRID_COLS
        cell_h = (bottom - top + 1) / GRID_ROWS
        if cell_w < 4 or cell_h < 4:
            return None
        px = im.load()
        bits: list[int] = []
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                cx = int(left + col * cell_w + cell_w / 2)
                cy = int(top + row * cell_h + cell_h / 2)
                bits.append(1 if _luma(px[cx, cy]) >= LUMA_THRESH else 0)

    raw = bytearray()
    for byte_idx in range(TOTAL_BYTES):
        b = 0
        for bit_idx in range(8):
            b = (b << 1) | bits[byte_idx * 8 + bit_idx]
        raw.append(b)

    magic_ok = raw[0] == MAGIC
    checksum_ok = (sum(raw[:63]) % 256) == raw[63]

    u16 = lambda i: (raw[i] << 8) | raw[i + 1]
    u24 = lambda i: (raw[i] << 16) | (raw[i + 1] << 8) | raw[i + 2]

    flags12 = raw[12]
    flags29 = raw[29]

    return Decoded(
        magic_ok=magic_ok,
        checksum_ok=checksum_ok,
        tick=raw[1],
        hp=u16(2),
        hp_max=u16(4),
        mp=u16(6),
        mp_max=u16(8),
        level=(raw[10] >> 1) & 0x7F,
        is_resting=bool(raw[10] & 0x01),
        class_id=(raw[11] >> 4) & 0x0F,
        race_id=raw[11] & 0x0F,
        in_combat=bool(flags12 & 0x80),
        gender=1 if (flags12 & 0x40) else 0,
        faction=1 if (flags12 & 0x20) else 0,
        mounted=bool(flags12 & 0x10),
        pvp_flagged=bool(flags12 & 0x08),
        grouped=bool(flags12 & 0x04),
        has_pet=bool(flags12 & 0x02),
        xp_pct=(raw[13] >> 1) & 0x7F,
        rested_xp=bool(raw[13] & 0x01),
        zone_hash=u16(14),
        map_x=raw[16],
        map_y=raw[17],
        facing=raw[18],
        durability_pct=(raw[19] >> 1) & 0x7F,
        bag_full=bool(raw[19] & 0x01),
        gold=u24(20),
        bag_free=raw[23],
        target_hp=u16(24),
        target_hp_max=u16(26),
        target_level=(raw[28] >> 1) & 0x7F,
        has_target=bool(raw[28] & 0x01),
        target_hostile=bool(flags29 & 0x80),
        target_is_player=bool(flags29 & 0x40),
        target_classification=(flags29 >> 3) & 0x07,
        target_cast_spell=u16(30),
        target_cast_progress=raw[32],
        player_cast_spell=u16(33),
        player_cast_progress=raw[35],
        buffs=[u16(36 + i * 2) for i in range(4)],
        debuffs=[u16(44 + i * 2) for i in range(4)],
        action_cooldowns=list(raw[52:62]),
        combo_points=(raw[62] >> 5) & 0x07,
        power_type=(raw[62] >> 2) & 0x07,
        raw_bytes=bytes(raw),
    )


def _pct(num: int, den: int) -> int:
    if den <= 0:
        return 0
    p = (num * 100) // den
    return max(0, min(100, p))


def to_event(d: Decoded) -> dict[str, Any]:
    target: dict[str, Any] | None = None
    if d.has_target:
        target = {
            "exists": True,
            "hostile": d.target_hostile,
            "isPlayer": d.target_is_player,
            "classification": CLASSIFICATIONS[d.target_classification],
            "level": d.target_level,
            "hp": d.target_hp,
            "hpMax": d.target_hp_max,
            "hpPct": _pct(d.target_hp, d.target_hp_max),
            "cast": {
                "spellId": d.target_cast_spell,
                "progress": d.target_cast_progress,
            } if d.target_cast_spell else None,
        }
    return {
        "t": "snapshot",
        "data": {
            "tick": d.tick,
            "player": {
                "hp": d.hp, "hpMax": d.hp_max, "hpPct": _pct(d.hp, d.hp_max),
                "mp": d.mp, "mpMax": d.mp_max, "mpPct": _pct(d.mp, d.mp_max),
                "level": d.level,
                "class": CLASS_NAMES.get(d.class_id, "?"),
                "classId": d.class_id,
                "race": RACE_NAMES.get(d.race_id, "?"),
                "raceId": d.race_id,
                "gender": "F" if d.gender else "M",
                "faction": "Horde" if d.faction else "Alliance",
                "mounted": d.mounted,
                "pvp": d.pvp_flagged,
                "grouped": d.grouped,
                "hasPet": d.has_pet,
                "resting": d.is_resting,
                "xpPct": d.xp_pct,
                "restedXp": d.rested_xp,
                "gold": d.gold,
                "bagFree": d.bag_free,
                "bagFull": d.bag_full,
                "durabilityPct": d.durability_pct,
                "powerType": POWER_TYPES.get(d.power_type, "?"),
                "comboPoints": d.combo_points,
                "cast": {
                    "spellId": d.player_cast_spell,
                    "progress": d.player_cast_progress,
                } if d.player_cast_spell else None,
            },
            "zone": {
                "hash": d.zone_hash,
                "mapX": d.map_x,
                "mapY": d.map_y,
                "facing": d.facing,
            },
            "combat": d.in_combat,
            "target": target,
            "buffs":   [b for b in d.buffs   if b > 0],
            "debuffs": [b for b in d.debuffs if b > 0],
            "actionCooldowns": d.action_cooldowns,
        },
    }
