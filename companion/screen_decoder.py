"""Decode the ASCIIMUD ScreenGrid from a WoW screenshot.

Mirrors addon/stream/ScreenGrid.lua. Schema version 2: grid is 128 cols x 16
rows = 2048 cells = 256 bytes per tick. White cell = 1, black cell = 0.

Schema v2 layout (see ScreenGrid.lua for the canonical bit layout):
    bytes 0..62   v1 fields (preserved verbatim from schema v1)
    byte  63      schema version (= 2; was checksum in v1)
    bytes 64..93  3 quests x 10 bytes each (id u24, mapX, mapY, 4 obj nibbles, flags)
    bytes 94..95  subzone hash u16
    bytes 96..99  world coords (i16, i16; raw WoW coord / 4)
    byte  100     threat % (0-100)
    byte  101     ambient flags (rare/elite/boss/enemyPlayer/channel/.../ghost)
    byte  102     pet hp %
    byte  103     pet level
    byte  104     pet flags (happiness, exists)
    bytes 105..108 reputation (factionID u16, bar %, tier nibble)
    bytes 109..111 talents (3 trees, points spent each)
    bytes 112..116 top 5 skills (0-255 scaled from 0-300)
    byte  117     party member count (0-4)
    bytes 118..129 4 mates x 3 bytes (class<<4|race, level, hp%)
    bytes 130..134 death recap (killer hash, spell, ticks-since)
    bytes 135..138 loot roll (item u24, my roll)
    bytes 139..144 last NPC chat (speaker hash, text hash, ticks-since, kind)
    bytes 145..152 cast targets + total ms (player, target)
    bytes 153..170 6 bag samples (item u16, count u8)
    bytes 171..218 16 equipment slots (item u24)
    bytes 219..234 expanded buffs slots 5..8 (id u16, stack u8, dur u8)
    bytes 235..250 expanded debuffs slots 5..8
    bytes 251..254 reserved
    byte  255     checksum = sum(bytes 0..254) % 256
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
GRID_COLS    = 128
GRID_ROWS    = 16
TOTAL_BYTES  = (GRID_COLS * GRID_ROWS) // 8     # 256
TOTAL_CELLS  = GRID_COLS * GRID_ROWS            # 2048
SIZE_W       = CELL_PX * GRID_COLS              # 1536 px
SIZE_H       = CELL_PX * GRID_ROWS              # 192 px
QUIET_PX     = 12                               # black border the addon adds
MAGIC        = 0xA5
SCHEMA_VER   = 2
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
REP_TIERS = ["unknown", "Hated", "Hostile", "Unfriendly", "Neutral",
             "Friendly", "Honored", "Revered", "Exalted"]
NPC_CHAT_KINDS = ["say", "yell", "emote", "monster_party", "whisper"]


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
    schema_version: int
    schema_ok: bool
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
    gender: int
    faction: int
    mounted: bool
    pvp_flagged: bool
    grouped: bool
    has_pet: bool
    xp_pct: int
    rested_xp: bool
    zone_hash: int
    subzone_hash: int
    map_x: int
    map_y: int
    world_x: int
    world_y: int
    facing: int
    durability_pct: int
    bag_full: bool
    gold: int
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
    target_cast_total_ms: int
    target_cast_target_hash: int
    player_cast_spell: int
    player_cast_progress: int
    player_cast_total_ms: int
    player_cast_target_hash: int
    threat_pct: int
    ambient_flags: int
    buffs: list[int] = field(default_factory=list)
    debuffs: list[int] = field(default_factory=list)
    buffs_ext: list[dict] = field(default_factory=list)
    debuffs_ext: list[dict] = field(default_factory=list)
    action_cooldowns: list[int] = field(default_factory=list)
    combo_points: int = 0
    power_type: int = 0
    quests: list[dict] = field(default_factory=list)
    pet_hp_pct: int = 0
    pet_level: int = 0
    pet_happiness: int = 0
    pet_exists: bool = False
    rep_faction_id: int = 0
    rep_bar_pct: int = 0
    rep_tier: int = 0
    talents: list[int] = field(default_factory=list)
    skills: list[int] = field(default_factory=list)
    group_count: int = 0
    group_mates: list[dict] = field(default_factory=list)
    death_killer_hash: int = 0
    death_spell_id: int = 0
    death_ticks_since: int = 0
    loot_item_id: int = 0
    loot_my_roll: int = 0
    npc_chat_speaker_hash: int = 0
    npc_chat_text_hash: int = 0
    npc_chat_ticks_since: int = 0
    npc_chat_kind: int = 0
    bag_samples: list[dict] = field(default_factory=list)
    equipment: list[int] = field(default_factory=list)
    raw_bytes: bytes = b""


def _luma(px) -> int:
    r, g, b = px[:3]
    return (r * 299 + g * 587 + b * 114) // 1000


def _find_grid_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    """Find the white cells in the bottom-right corner."""
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


def _i16(hi: int, lo: int) -> int:
    v = (hi << 8) | lo
    if v >= 0x8000:
        v -= 0x10000
    return v


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
    checksum_ok = (sum(raw[:255]) % 256) == raw[255]
    schema_version = raw[63]
    schema_ok = schema_version == SCHEMA_VER

    u16 = lambda i: (raw[i] << 8) | raw[i + 1]
    u24 = lambda i: (raw[i] << 16) | (raw[i + 1] << 8) | raw[i + 2]
    i16 = lambda i: _i16(raw[i], raw[i + 1])

    flags12 = raw[12]
    flags29 = raw[29]

    quests = []
    for q in range(3):
        base = 64 + q * 10
        qid = u24(base)
        if qid == 0:
            continue
        objs = []
        for o in range(4):
            byte = raw[base + 5 + o]
            cur_n = (byte >> 4) & 0x0F
            req_n = byte & 0x0F
            if req_n > 0:
                objs.append({"cur": cur_n, "req": req_n,
                             "pct": int((cur_n / 15) * 100)})
        quests.append({
            "id": qid,
            "mapX": raw[base + 3],
            "mapY": raw[base + 4],
            "objectives": objs,
            "complete": bool(raw[base + 9] & 0x80),
        })

    mates = []
    for m in range(4):
        base = 118 + m * 3
        cr = raw[base]
        if cr == 0 and raw[base + 1] == 0:
            continue
        mates.append({
            "classId": (cr >> 4) & 0x0F,
            "raceId": cr & 0x0F,
            "level": raw[base + 1],
            "hpPct": raw[base + 2],
        })

    bag_samples = []
    for i in range(6):
        base = 153 + i * 3
        item_id = u16(base)
        count = raw[base + 2]
        if item_id > 0:
            bag_samples.append({"itemId": item_id, "count": count})

    equipment = [u24(171 + i * 3) for i in range(16)]

    buffs_ext = []
    for i in range(4):
        base = 219 + i * 4
        sid = u16(base)
        if sid > 0:
            buffs_ext.append({"id": sid, "stacks": raw[base + 2],
                              "duration": raw[base + 3]})
    debuffs_ext = []
    for i in range(4):
        base = 235 + i * 4
        sid = u16(base)
        if sid > 0:
            debuffs_ext.append({"id": sid, "stacks": raw[base + 2],
                                "duration": raw[base + 3]})

    return Decoded(
        magic_ok=magic_ok,
        checksum_ok=checksum_ok,
        schema_version=schema_version,
        schema_ok=schema_ok,
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
        subzone_hash=u16(94),
        map_x=raw[16],
        map_y=raw[17],
        world_x=i16(96),
        world_y=i16(98),
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
        target_cast_total_ms=u16(151),
        target_cast_target_hash=u16(149),
        player_cast_spell=u16(33),
        player_cast_progress=raw[35],
        player_cast_total_ms=u16(147),
        player_cast_target_hash=u16(145),
        threat_pct=raw[100],
        ambient_flags=raw[101],
        buffs=[u16(36 + i * 2) for i in range(4)],
        debuffs=[u16(44 + i * 2) for i in range(4)],
        buffs_ext=buffs_ext,
        debuffs_ext=debuffs_ext,
        action_cooldowns=list(raw[52:62]),
        combo_points=(raw[62] >> 5) & 0x07,
        power_type=(raw[62] >> 2) & 0x07,
        quests=quests,
        pet_hp_pct=raw[102],
        pet_level=raw[103],
        pet_happiness=(raw[104] >> 6) & 0x03,
        pet_exists=bool(raw[104] & 0x20),
        rep_faction_id=u16(105),
        rep_bar_pct=raw[107],
        rep_tier=(raw[108] >> 4) & 0x0F,
        talents=[raw[109], raw[110], raw[111]],
        skills=list(raw[112:117]),
        group_count=raw[117],
        group_mates=mates,
        death_killer_hash=u16(130),
        death_spell_id=u16(132),
        death_ticks_since=raw[134],
        loot_item_id=u24(135),
        loot_my_roll=raw[138],
        npc_chat_speaker_hash=u16(139),
        npc_chat_text_hash=u16(141),
        npc_chat_ticks_since=raw[143],
        npc_chat_kind=raw[144],
        bag_samples=bag_samples,
        equipment=equipment,
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
                "totalMs": d.target_cast_total_ms,
                "targetHash": d.target_cast_target_hash,
            } if d.target_cast_spell else None,
        }

    pet = None
    if d.pet_exists:
        pet = {
            "hpPct": d.pet_hp_pct,
            "level": d.pet_level,
            "happiness": d.pet_happiness,
        }

    death = None
    if d.death_killer_hash > 0 and d.death_ticks_since < 200:
        death = {
            "killerHash": d.death_killer_hash,
            "spellId": d.death_spell_id,
            "ticksSince": d.death_ticks_since,
        }

    loot = None
    if d.loot_item_id > 0:
        loot = {"itemId": d.loot_item_id, "myRoll": d.loot_my_roll}

    npc_chat = None
    if d.npc_chat_speaker_hash > 0 and d.npc_chat_ticks_since < 200:
        kind = NPC_CHAT_KINDS[d.npc_chat_kind] if d.npc_chat_kind < len(NPC_CHAT_KINDS) else "?"
        npc_chat = {
            "speakerHash": d.npc_chat_speaker_hash,
            "textHash": d.npc_chat_text_hash,
            "ticksSince": d.npc_chat_ticks_since,
            "kind": kind,
        }

    reputation = None
    if d.rep_faction_id > 0:
        reputation = {
            "factionId": d.rep_faction_id,
            "barPct": d.rep_bar_pct,
            "tier": d.rep_tier,
            "tierName": REP_TIERS[d.rep_tier] if d.rep_tier < len(REP_TIERS) else "?",
        }

    flags = d.ambient_flags
    flags_obj = {
        "rareNearby": bool(flags & 0x01),
        "eliteNearby": bool(flags & 0x02),
        "bossNearby": bool(flags & 0x04),
        "enemyPlayerNearby": bool(flags & 0x08),
        "playerChanneling": bool(flags & 0x10),
        "targetChanneling": bool(flags & 0x20),
        "stealthed": bool(flags & 0x40),
        "ghost": bool(flags & 0x80),
    }

    return {
        "t": "snapshot",
        "data": {
            "tick": d.tick,
            "schemaVersion": d.schema_version,
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
                    "totalMs": d.player_cast_total_ms,
                    "targetHash": d.player_cast_target_hash,
                } if d.player_cast_spell else None,
            },
            "zone": {
                "hash": d.zone_hash,
                "subzoneHash": d.subzone_hash,
                "mapX": d.map_x,
                "mapY": d.map_y,
                "worldX": d.world_x,
                "worldY": d.world_y,
                "facing": d.facing,
            },
            "combat": d.in_combat,
            "threat": d.threat_pct,
            "flags": flags_obj,
            "target": target,
            "pet": pet,
            "buffs":   [b for b in d.buffs   if b > 0],
            "debuffs": [b for b in d.debuffs if b > 0],
            "buffsExt": d.buffs_ext,
            "debuffsExt": d.debuffs_ext,
            "actionCooldowns": d.action_cooldowns,
            "quests": d.quests,
            "reputation": reputation,
            "talents": d.talents,
            "skills": d.skills,
            "group": {
                "count": d.group_count,
                "mates": [
                    {**m, "class": CLASS_NAMES.get(m["classId"], "?"),
                     "race": RACE_NAMES.get(m["raceId"], "?")}
                    for m in d.group_mates
                ],
            },
            "death": death,
            "loot": loot,
            "npcChat": npc_chat,
            "bag": d.bag_samples,
            "equipment": [e for e in d.equipment if e > 0],
            "equipmentSlots": d.equipment,
        },
    }
