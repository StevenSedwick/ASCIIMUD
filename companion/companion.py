"""ASCIIMUD companion process.

Tails the WoW logs the game engine writes to disk:
  * ``WoWCombatLog.txt`` — every combat event involving the player
  * ``WoWChatLog.txt``   — chat events (zone notices, system messages, etc.)

Maintains an authoritative state store and broadcasts events + snapshots over
a WebSocket on ``ws://<host>:<port>/ws`` for the OBS overlay (and the EBS).

Usage:
    pip install -r requirements.txt
    cp config.example.toml config.toml   # edit log_path
    python companion.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
import tomllib
from pathlib import Path
from typing import Any

from aiohttp import WSMsgType, web

from combatlog import parse as parse_combat

try:
    import websockets  # type: ignore
except ImportError:  # pragma: no cover - optional EBS forwarding
    websockets = None  # type: ignore

LOG = logging.getLogger("asciimud.companion")
PREFIX = "ASCIIMUD~"
COALESCE_WINDOW = 1.5  # seconds to bucket melee/spell repeats


class StateStore:
    def __init__(self) -> None:
        self.snapshot: dict[str, Any] = {}
        self.severity: int = 0
        self.player_name: str | None = None
        self.last_target: str | None = None

    def apply(self, evt: dict[str, Any]) -> None:
        t = evt.get("t")
        if t == "snapshot":
            self.snapshot = evt.get("data", {})
        elif t == "severity":
            self.severity = int(evt.get("level", 0))
        elif t == "combat":
            # Track who you're hitting / who's hitting you.
            if evt.get("src") and evt.get("src") == self.player_name:
                if evt.get("dst"):
                    self.last_target = evt["dst"]


class Coalescer:
    """Bucket repeated combat hits within COALESCE_WINDOW into summary events."""

    def __init__(self, hub: "Hub", player_name_getter) -> None:
        self.hub = hub
        self.get_player = player_name_getter
        # key = (event, spell, src->dst) -> {count, total, last_ts}
        self.buckets: dict[tuple, dict[str, Any]] = {}
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._flusher())

    async def _flusher(self) -> None:
        while True:
            await asyncio.sleep(0.5)
            now = time.monotonic()
            ready = [k for k, b in self.buckets.items() if now - b["last"] > COALESCE_WINDOW]
            for k in ready:
                b = self.buckets.pop(k)
                event, spell, direction = k
                payload = {
                    "t": "combat_summary",
                    "event": event,
                    "spell": spell,
                    "direction": direction,
                    "count": b["count"],
                    "total": b["total"],
                    "src": b["src"],
                    "dst": b["dst"],
                }
                await self.hub.broadcast(payload)

    def add(self, evt: dict[str, Any]) -> None:
        event = evt["event"]
        if event == "UNIT_DIED":
            # No bucketing — broadcast immediately.
            asyncio.create_task(self.hub.broadcast(evt))
            return
        spell = evt.get("spell", "")
        player = self.get_player()
        src, dst = evt.get("src"), evt.get("dst")
        if player and src == player:
            direction = "out"
        elif player and dst == player:
            direction = "in"
        else:
            direction = "other"
        key = (event, spell, direction)
        b = self.buckets.get(key)
        if b is None:
            b = {"count": 0, "total": 0, "last": 0.0, "src": src, "dst": dst}
            self.buckets[key] = b
        b["count"] += 1
        b["total"] += int(evt.get("amount", 0) or 0)
        b["last"] = time.monotonic()


class Hub:
    def __init__(self) -> None:
        self.clients: set[web.WebSocketResponse] = set()

    async def broadcast(self, payload: dict[str, Any]) -> None:
        if not self.clients:
            return
        msg = json.dumps(payload)
        dead = []
        for ws in self.clients:
            try:
                await ws.send_str(msg)
            except ConnectionResetError:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)


class EBSForwarder:
    """Maintains an outbound WSS to the cloud EBS and forwards every event.

    Reconnects on failure with exponential backoff; drops events while
    disconnected (the EBS keeps last-known state per channel anyway).
    """

    def __init__(self, url: str, channel_id: str, shared_secret: str) -> None:
        self.url = url.rstrip("/") + f"/ingest?channel={channel_id}&token={shared_secret}"
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1024)
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if websockets is None:
            LOG.warning("EBS forwarding configured but `websockets` not installed.")
            return
        self._task = asyncio.create_task(self._run())

    async def submit(self, evt_json: str) -> None:
        try:
            self.queue.put_nowait(evt_json)
        except asyncio.QueueFull:
            LOG.debug("EBS queue full, dropping event")

    async def _run(self) -> None:
        backoff = 1.0
        while True:
            try:
                LOG.info("Connecting to EBS %s", self.url.split("?")[0])
                async with websockets.connect(self.url, max_size=2 ** 20) as ws:
                    backoff = 1.0
                    LOG.info("EBS connected")
                    while True:
                        line = await self.queue.get()
                        await ws.send(line)
            except Exception as exc:  # noqa: BLE001 - keep reconnecting
                LOG.warning("EBS link down (%s); retry in %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(30.0, backoff * 2)


async def tail(path: Path, on_line) -> None:
    LOG.info("Tailing %s", path)
    while not path.exists():
        LOG.warning("Log not found yet: %s (retrying)", path)
        await asyncio.sleep(2)
    with path.open("r", encoding="utf-8", errors="replace") as f:
        f.seek(0, 2)  # jump to EOF; we only want new lines
        while True:
            line = f.readline()
            if not line:
                # On Windows, TextIOWrapper caches EOF — seek refreshes it.
                f.seek(f.tell())
                await asyncio.sleep(0.1)
                continue
            await on_line(line.rstrip("\r\n"))


async def tail_glob(directory: Path, pattern: str, on_line, label: str = "") -> None:
    """Tail the newest file matching ``pattern`` in ``directory``.

    Auto-switches to a newer matching file when one appears. The very first
    file (at startup) is opened at EOF so we don't replay ancient sessions;
    every *rotated-in* file is read from byte 0, because the tick-flush
    addon closes one file and opens the next mid-session and the new file
    contains only fresh data we want to ingest in full.
    """
    LOG.info("Tail-glob %s/%s (%s)", directory, pattern, label or "newest")

    def newest() -> Path | None:
        if not directory.exists():
            return None
        files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime)
        return files[-1] if files else None

    current: Path | None = None
    f = None
    is_first = True
    try:
        while True:
            latest = newest()
            if latest is None:
                if current is not None:
                    LOG.warning("No %s files in %s; waiting…", pattern, directory)
                    if f is not None:
                        f.close()
                        f = None
                    current = None
                await asyncio.sleep(2)
                continue
            if latest != current:
                if f is not None:
                    f.close()
                LOG.info("Tailing %s%s", latest, " (from EOF)" if is_first else " (from start)")
                f = latest.open("r", encoding="utf-8", errors="replace")
                if is_first:
                    f.seek(0, 2)
                    is_first = False
                current = latest
            assert f is not None
            line = f.readline()
            if not line:
                # Windows TextIOWrapper caches EOF — re-seek to refresh.
                f.seek(f.tell())
                # Periodically re-scan in case a new file appeared.
                await asyncio.sleep(0.25)
                continue
            await on_line(line.rstrip("\r\n"))
    finally:
        if f is not None:
            f.close()


async def ingest(line: str, store: StateStore, hub: Hub,
                 ebs: EBSForwarder | None) -> None:
    idx = line.find(PREFIX)
    if idx < 0:
        return
    raw = line[idx + len(PREFIX):]
    try:
        evt = json.loads(raw)
    except json.JSONDecodeError:
        LOG.debug("Bad JSON: %s", raw[:120])
        return
    store.apply(evt)
    await hub.broadcast(evt)
    if ebs is not None:
        await ebs.submit(raw)


async def ingest_combat(line: str, store: StateStore,
                        coalescer: Coalescer, ebs: EBSForwarder | None) -> None:
    evt = parse_combat(line)
    if evt is None:
        return
    store.apply(evt)
    coalescer.add(evt)
    if ebs is not None:
        await ebs.submit(json.dumps(evt))


async def watch_screenshots(directory: Path, pattern: str, store: StateStore,
                            hub: Hub, ebs: EBSForwarder | None,
                            keep_last: int = 4) -> None:
    """Decode every new screenshot dropping into ``directory`` matching
    ``pattern`` and broadcast as a snapshot. Old shots are deleted to keep
    disk usage bounded (we only need the newest)."""
    from screen_decoder import decode, to_event  # local import — needs Pillow

    LOG.info("Watching screenshots: %s/%s", directory, pattern)
    seen: set[Path] = set()
    # Don't reprocess shots taken before the companion started.
    if directory.exists():
        for p in directory.glob(pattern):
            seen.add(p)

    while True:
        if not directory.exists():
            await asyncio.sleep(2)
            continue
        files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime)
        new = [p for p in files if p not in seen]
        for p in new:
            seen.add(p)
            # Wait a beat for WoW to finish writing.
            await asyncio.sleep(0.05)
            try:
                d = decode(p)
            except Exception as exc:  # noqa: BLE001
                LOG.warning("Decode failed for %s: %s", p.name, exc)
                continue
            if d is None or not d.magic_ok:
                # Likely a manual screenshot (no grid). Ignore.
                continue
            if not d.checksum_ok:
                LOG.debug("Checksum mismatch on %s", p.name)
                continue
            evt = to_event(d)
            LOG.info("Snapshot tick=%d hp=%d%% mp=%d%% combat=%s zone=0x%X",
                     d.tick, d.hp_pct, d.mp_pct, d.in_combat, d.zone_hash)
            store.apply(evt)
            await hub.broadcast(evt)
            if ebs is not None:
                await ebs.submit(json.dumps(evt))

        # Trim old shots — keep only the newest `keep_last` of OUR screenshots.
        if len(files) > keep_last:
            for old in files[:-keep_last]:
                try:
                    old.unlink()
                    seen.discard(old)
                except OSError:
                    pass

        await asyncio.sleep(0.5)


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    hub: Hub = request.app["hub"]
    store: StateStore = request.app["store"]
    hub.clients.add(ws)
    LOG.info("Client connected (%d total)", len(hub.clients))
    # Greet with current state so the overlay paints immediately.
    if store.snapshot:
        await ws.send_str(json.dumps({"t": "snapshot", "data": store.snapshot}))
    await ws.send_str(json.dumps({"t": "severity", "level": store.severity}))
    try:
        async for msg in ws:
            if msg.type == WSMsgType.ERROR:
                break
    finally:
        hub.clients.discard(ws)
        LOG.info("Client disconnected (%d total)", len(hub.clients))
    return ws


async def index(_: web.Request) -> web.Response:
    return web.Response(text="ASCIIMUD companion online. Connect to /ws.")


def load_config() -> dict[str, Any]:
    cfg_path = Path(__file__).with_name("config.toml")
    if not cfg_path.exists():
        cfg_path = Path(__file__).with_name("config.example.toml")
    with cfg_path.open("rb") as f:
        return tomllib.load(f)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    cfg = load_config()
    log_path = Path(cfg["wow"]["log_path"]).expanduser()
    log_dir = Path(cfg["wow"].get("log_dir", str(log_path.parent))).expanduser()
    combat_log_pattern = cfg["wow"].get("combat_log_pattern", "WoWCombatLog*.txt")
    chat_log_pattern = cfg["wow"].get("chat_log_pattern", "WoWChatLog*.txt")
    screenshots_dir = Path(cfg["wow"].get(
        "screenshots_dir",
        str(log_path.parent.parent / "Screenshots")
    )).expanduser()
    screenshots_pattern = cfg["wow"].get("screenshots_pattern", "WoWScrnShot_*.jpg")
    host = cfg["server"].get("host", "127.0.0.1")
    port = int(cfg["server"].get("port", 8765))

    store = StateStore()
    hub = Hub()
    coalescer = Coalescer(hub, lambda: store.player_name)
    coalescer.start()

    ebs: EBSForwarder | None = None
    ecfg = cfg.get("ebs", {})
    if ecfg.get("url"):
        ebs = EBSForwarder(
            url=ecfg["url"],
            channel_id=str(ecfg.get("channel_id", "")),
            shared_secret=ecfg.get("shared_secret", ""),
        )
        ebs.start()

    app = web.Application()
    app["store"] = store
    app["hub"] = hub
    app.router.add_get("/", index)
    app.router.add_get("/ws", ws_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    LOG.info("WebSocket server on ws://%s:%d/ws", host, port)
    LOG.info("Watching %s for %s and %s", log_dir, chat_log_pattern, combat_log_pattern)
    LOG.info("Watching screenshots in %s", screenshots_dir)

    await asyncio.gather(
        tail_glob(log_dir, chat_log_pattern,
                  lambda l: ingest(l, store, hub, ebs), label="chat"),
        tail_glob(log_dir, combat_log_pattern,
                  lambda l: ingest_combat(l, store, coalescer, ebs), label="combat"),
        watch_screenshots(screenshots_dir, screenshots_pattern,
                          store, hub, ebs),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
