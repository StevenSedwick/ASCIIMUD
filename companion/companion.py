"""ASCIIMUD companion process.

Tails ``WoWChatLog.txt``, parses ``ASCIIMUD|{json}`` lines emitted by the addon,
maintains an authoritative state store, and broadcasts events + snapshots over a
WebSocket on ``ws://<host>:<port>/ws`` for the OBS overlay (and, later, the EBS).

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
import tomllib
from pathlib import Path
from typing import Any

from aiohttp import WSMsgType, web

LOG = logging.getLogger("asciimud.companion")
PREFIX = "ASCIIMUD|"


class StateStore:
    def __init__(self) -> None:
        self.snapshot: dict[str, Any] = {}
        self.severity: int = 0

    def apply(self, evt: dict[str, Any]) -> None:
        t = evt.get("t")
        if t == "snapshot":
            self.snapshot = evt.get("data", {})
        elif t == "severity":
            self.severity = int(evt.get("level", 0))


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
                await asyncio.sleep(0.1)
                continue
            await on_line(line.rstrip("\r\n"))


async def ingest(line: str, store: StateStore, hub: Hub) -> None:
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
    host = cfg["server"].get("host", "127.0.0.1")
    port = int(cfg["server"].get("port", 8765))

    store = StateStore()
    hub = Hub()

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

    await tail(log_path, lambda l: ingest(l, store, hub))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
