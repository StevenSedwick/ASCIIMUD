"""Zone-hash → name lookup. Mirrors overlay/app.js ZONE_NAMES.

The screen-grid carries `zone.hash` (u16, polynomial hash of GetZoneText()).
Match the addon and overlay tables exactly so the same hash resolves to the
same name in chat and on stream.
"""
from __future__ import annotations

ZONE_NAMES: dict[int, str] = {
    0xD3DE: "Alterac Mountains",     0xC54B: "Arathi Highlands",
    0x1763: "Ashenvale",             0x9722: "Azshara",
    0x35E7: "Azuremyst Isle",        0x4F23: "Badlands",
    0xF2DF: "Blasted Lands",         0x3ADC: "Bloodmyst Isle",
    0xEF25: "Burning Steppes",       0xEE97: "Darkshore",
    0xE0E6: "Darnassus",             0xC145: "Deadwind Pass",
    0x5CD4: "Desolace",              0x5043: "Dun Morogh",
    0x6A37: "Durotar",               0x2377: "Dustwallow Marsh",
    0x5FDA: "Eastern Plaguelands",   0x3ED4: "Elwynn Forest",
    0x7439: "Eversong Woods",        0x6019: "Exodar",
    0x5B9A: "Felwood",               0xDB90: "Feralas",
    0x5ED9: "Ghostlands",            0x81C9: "Hillsbrad Foothills",
    0x36D4: "Hinterlands",           0xF37F: "Ironforge",
    0x41B7: "Loch Modan",            0xA31C: "Moonglade",
    0x3EBF: "Mulgore",               0x604C: "Orgrimmar",
    0xC7A0: "Redridge Mountains",    0xE247: "Searing Gorge",
    0x3105: "Silithus",              0x7EBD: "Silvermoon City",
    0x23A0: "Silverpine Forest",     0x0C9F: "Stonetalon Mountains",
    0xDBFA: "Stormwind City",        0x4AEF: "Stranglethorn Vale",
    0x2E66: "Swamp of Sorrows",      0x701C: "Tanaris",
    0x5F3B: "Teldrassil",            0x30DC: "The Barrens",
    0x3985: "The Hinterlands",       0xD682: "Thousand Needles",
    0x10EF: "Thunder Bluff",         0xA82C: "Tirisfal Glades",
    0xDB1C: "Un'Goro Crater",        0xD023: "Undercity",
    0xC7E8: "Western Plaguelands",   0x6DCA: "Westfall",
    0x7462: "Wetlands",              0x8532: "Winterspring",
}


def name(hash_: int | None) -> str:
    if hash_ is None:
        return "Unknown"
    return ZONE_NAMES.get(int(hash_), f"zone#{int(hash_):04X}")
