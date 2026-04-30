"""Decode the ASCIIMUD ScreenGrid from a WoW screenshot.

The addon renders an 8x8 grid of black/white squares in the bottom-right
corner of the WoW window:
    * each cell is CELL_PX pixels square
    * grid is anchored CORNER_OFF_X from the right edge,
      CORNER_OFF_Y from the bottom edge
    * white = 1, black = 0
    * cells read row-major, top-left first

Schema (must mirror addon/stream/ScreenGrid.lua):
    byte0  = magic = 0xA5
    byte1  = tick % 256
    byte2  = bits 7..1: HP%, bit 0: in_combat
    byte3  = bits 7..1: MP%, bit 0: target_hostile
    byte4..5 = zone hash (16 bits, big-endian)
    byte6  = bits 7..1: target_hp%, bit 0: has_target
    byte7  = checksum = sum(byte0..byte6) % 256
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError as e:  # pragma: no cover - hard dep
    raise SystemExit("Install Pillow: pip install Pillow") from e

CELL_PX      = 12
GRID_CELLS   = 8
CORNER_OFF_X = 8
CORNER_OFF_Y = 8
SIZE_PX      = CELL_PX * GRID_CELLS
MAGIC        = 0xA5

# White/black threshold on luminance (0..255). JPG compression smears edges,
# so we sample the centre of each cell where the colour is strongest.
LUMA_THRESH = 128


@dataclass
class Decoded:
    magic_ok: bool
    checksum_ok: bool
    tick: int
    hp_pct: int
    mp_pct: int
    in_combat: bool
    target_hostile: bool
    has_target: bool
    target_hp_pct: int
    zone_hash: int
    raw_bytes: bytes


def _luma(px) -> int:
    r, g, b = px[:3]
    return (r * 299 + g * 587 + b * 114) // 1000


def _find_grid_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    """Auto-detect the grid bounding box in the bottom-right ~200x200 region.
    Returns (left, top, right, bottom) inclusive or None if no white pixels found.
    """
    w, h = img.size
    search_w = min(110, w)
    search_h = min(110, h)
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
    """Decode a screenshot file. Returns None if the magic byte is wrong
    (likely a screenshot taken before the grid existed, or grid hidden)."""
    with Image.open(path) as im:
        im = im.convert("RGB")
        bbox = _find_grid_bbox(im)
        if bbox is None:
            return None
        left, top, right, bottom = bbox
        # Cell size from bounding box; +1 because bbox is inclusive.
        cell_w = (right - left + 1) / GRID_CELLS
        cell_h = (bottom - top + 1) / GRID_CELLS
        # Sanity: cells need a minimum width to decode reliably.
        if cell_w < 4 or cell_h < 4:
            return None
        px = im.load()
        bits: list[int] = []
        for row in range(GRID_CELLS):
            for col in range(GRID_CELLS):
                cx = int(left + col * cell_w + cell_w / 2)
                cy = int(top + row * cell_h + cell_h / 2)
                bits.append(1 if _luma(px[cx, cy]) >= LUMA_THRESH else 0)

    raw = bytearray()
    for byte_idx in range(8):
        b = 0
        for bit_idx in range(8):
            b = (b << 1) | bits[byte_idx * 8 + bit_idx]
        raw.append(b)

    magic_ok = raw[0] == MAGIC
    checksum_ok = (sum(raw[:7]) % 256) == raw[7]
    return Decoded(
        magic_ok=magic_ok,
        checksum_ok=checksum_ok,
        tick=raw[1],
        hp_pct=(raw[2] >> 1) & 0x7F,
        in_combat=bool(raw[2] & 0x01),
        mp_pct=(raw[3] >> 1) & 0x7F,
        target_hostile=bool(raw[3] & 0x01),
        zone_hash=(raw[4] << 8) | raw[5],
        target_hp_pct=(raw[6] >> 1) & 0x7F,
        has_target=bool(raw[6] & 0x01),
        raw_bytes=bytes(raw),
    )


def to_event(d: Decoded) -> dict[str, Any]:
    target = None
    if d.has_target:
        target = {
            "exists": True,
            "hostile": d.target_hostile,
            "hpPct": d.target_hp_pct,
        }
    return {
        "t": "snapshot",
        "data": {
            "tick": d.tick,
            "player": {
                "hpPct": d.hp_pct,
                "mpPct": d.mp_pct,
            },
            "zone": {"hash": d.zone_hash},
            "combat": d.in_combat,
            "target": target,
        },
    }
