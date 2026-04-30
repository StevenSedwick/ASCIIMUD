"""ASCIIMUD Extension Backend Service (EBS).

Responsibilities:
  * Accept an authenticated outbound WebSocket from the home companion process
    and ingest its event stream.
  * Maintain the latest world state per channel.
  * Fan out a low-rate, size-capped *digest* to every viewer via Twitch PubSub.
  * Fan out a high-rate, full-fidelity stream to opted-in viewers via per-viewer
    WSS (authenticated with the Twitch helper JWT).

Run:
    pip install -r requirements.txt
    cp config.example.toml config.toml   # fill in extension client id/secret
    uvicorn server:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import tomllib
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import (
    Depends, FastAPI, Header, HTTPException, Query, WebSocket,
    WebSocketDisconnect, status,
)
from fastapi.responses import JSONResponse

from auth import VerifiedViewer, verify_viewer_jwt
from pubsub import PubSubPublisher
from ratelimit import TokenBucket

LOG = logging.getLogger("asciimud.ebs")

CONFIG_PATH = Path(__file__).with_name("config.toml")
if not CONFIG_PATH.exists():
    CONFIG_PATH = Path(__file__).with_name("config.example.toml")
with CONFIG_PATH.open("rb") as f:
    CFG = tomllib.load(f)

INGEST_SECRET: str = CFG["ingest"]["shared_secret"]
EXT_CLIENT_ID: str = CFG["twitch"]["client_id"]
EXT_SECRET_B64: str = CFG["twitch"]["extension_secret"]
OWNER_USER_ID: str = str(CFG["twitch"]["owner_user_id"])
DIGEST_HZ: float = float(CFG.get("limits", {}).get("digest_hz", 1.0))
RICH_HZ: float = float(CFG.get("limits", {}).get("rich_hz", 5.0))


class ChannelState:
    """Latest snapshot + severity per channel; what new viewers see on connect."""

    def __init__(self) -> None:
        self.snapshot: dict[str, Any] = {}
        self.severity: int = 0
        self.last_event_ts: float = 0.0

    def apply(self, evt: dict[str, Any]) -> None:
        t = evt.get("t")
        if t == "snapshot":
            self.snapshot = evt.get("data", {})
        elif t == "severity":
            self.severity = int(evt.get("level", 0))
        self.last_event_ts = time.time()

    def digest(self) -> dict[str, Any]:
        """5KB-safe summary suitable for PubSub broadcast."""
        s = self.snapshot
        p = s.get("player", {}) or {}
        z = s.get("zone", {}) or {}
        tgt = s.get("target") or None
        hp_pct = round(100 * (p.get("hp", 0) / p["hpMax"])) if p.get("hpMax") else 0
        return {
            "v": 1,
            "ts": int(self.last_event_ts),
            "sev": self.severity,
            "ch": s.get("chapter", 1),
            "z": z.get("subzone") or z.get("name") or "",
            "lvl": p.get("level"),
            "hpPct": hp_pct,
            "tgt": (tgt or {}).get("name"),
            "tgtHostile": bool((tgt or {}).get("hostile")),
        }


class Hub:
    """Per-channel set of viewer WebSockets."""

    def __init__(self) -> None:
        self.by_channel: dict[str, set[WebSocket]] = defaultdict(set)

    def add(self, channel: str, ws: WebSocket) -> None:
        self.by_channel[channel].add(ws)

    def remove(self, channel: str, ws: WebSocket) -> None:
        self.by_channel.get(channel, set()).discard(ws)

    async def broadcast(self, channel: str, payload: dict[str, Any]) -> None:
        peers = list(self.by_channel.get(channel, ()))
        if not peers:
            return
        msg = json.dumps(payload)
        for ws in peers:
            try:
                await ws.send_text(msg)
            except Exception:
                self.remove(channel, ws)


class App:
    def __init__(self) -> None:
        self.channels: dict[str, ChannelState] = defaultdict(ChannelState)
        self.hub = Hub()
        self.pubsub = PubSubPublisher(EXT_CLIENT_ID, EXT_SECRET_B64, OWNER_USER_ID)
        self.digest_buckets: dict[str, TokenBucket] = {}
        self.rich_buckets: dict[str, TokenBucket] = {}

    def digest_bucket(self, channel: str) -> TokenBucket:
        b = self.digest_buckets.get(channel)
        if b is None:
            b = TokenBucket(rate=DIGEST_HZ, capacity=2)
            self.digest_buckets[channel] = b
        return b

    def rich_bucket(self, channel: str) -> TokenBucket:
        b = self.rich_buckets.get(channel)
        if b is None:
            b = TokenBucket(rate=RICH_HZ, capacity=10)
            self.rich_buckets[channel] = b
        return b


STATE = App()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    LOG.info("EBS starting on owner_user_id=%s", OWNER_USER_ID)
    yield
    await STATE.pubsub.aclose()


app = FastAPI(title="ASCIIMUD EBS", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "channels": list(STATE.channels.keys()),
        "viewers": {ch: len(s) for ch, s in STATE.hub.by_channel.items()},
    }


# ---------------------------------------------------------------------------
# Companion ingest WS: server-to-server, authenticated by shared secret.
# URL: wss://ebs.example.com/ingest?channel=<channel_id>&token=<INGEST_SECRET>
# ---------------------------------------------------------------------------
@app.websocket("/ingest")
async def ingest_ws(ws: WebSocket,
                    channel: str = Query(...),
                    token: str = Query(...)) -> None:
    if token != INGEST_SECRET:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await ws.accept()
    LOG.info("Companion connected for channel=%s", channel)
    cstate = STATE.channels[channel]
    try:
        while True:
            raw = await ws.receive_text()
            try:
                evt = json.loads(raw)
            except json.JSONDecodeError:
                continue
            cstate.apply(evt)
            await _on_event(channel, cstate, evt)
    except WebSocketDisconnect:
        LOG.info("Companion disconnected channel=%s", channel)


async def _on_event(channel: str, cstate: ChannelState, evt: dict[str, Any]) -> None:
    # Rich (per-viewer WS): rate-limited but generous.
    if STATE.rich_bucket(channel).take():
        await STATE.hub.broadcast(channel, evt)
    # Digest (PubSub broadcast): hard 1Hz cap, size-capped payload.
    if STATE.digest_bucket(channel).take():
        try:
            await STATE.pubsub.send_broadcast(channel, cstate.digest())
        except Exception as exc:  # noqa: BLE001 - log + continue
            LOG.warning("PubSub send failed for %s: %s", channel, exc)


# ---------------------------------------------------------------------------
# Viewer WS: opted-in viewers get the rich stream. Authenticated with the
# Twitch helper JWT that the extension's frontend obtains via window.Twitch.ext.
# URL: wss://ebs.example.com/viewer?token=<jwt>
# ---------------------------------------------------------------------------
@app.websocket("/viewer")
async def viewer_ws(ws: WebSocket, token: str = Query(...)) -> None:
    try:
        viewer: VerifiedViewer = verify_viewer_jwt(token, EXT_SECRET_B64)
    except Exception as exc:  # noqa: BLE001
        LOG.info("Viewer rejected: %s", exc)
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    channel = viewer.channel_id
    await ws.accept()
    STATE.hub.add(channel, ws)
    LOG.info("Viewer connected channel=%s opaque=%s",
             channel, viewer.opaque_user_id)

    cstate = STATE.channels.get(channel)
    if cstate and cstate.snapshot:
        await ws.send_text(json.dumps({"t": "snapshot", "data": cstate.snapshot}))
        await ws.send_text(json.dumps({"t": "severity", "level": cstate.severity}))

    try:
        while True:
            # Viewer messages aren't used yet; future: per-viewer requests.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        STATE.hub.remove(channel, ws)


# ---------------------------------------------------------------------------
# Broadcaster config endpoints (used by extension config.html).
# ---------------------------------------------------------------------------
@app.get("/config/digest")
async def get_digest(token: str = Query(...)) -> JSONResponse:
    viewer = verify_viewer_jwt(token, EXT_SECRET_B64)
    cstate = STATE.channels.get(viewer.channel_id)
    return JSONResponse(cstate.digest() if cstate else {})


def _require_jwt(authorization: str = Header(default="")) -> VerifiedViewer:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1]
    return verify_viewer_jwt(token, EXT_SECRET_B64)


@app.post("/config/save")
async def save_config(
    payload: dict[str, Any],
    viewer: VerifiedViewer = Depends(_require_jwt),
) -> dict[str, Any]:
    if viewer.role != "broadcaster":
        raise HTTPException(status_code=403, detail="broadcaster only")
    # TODO: persist channel-level config. For now, echo back.
    LOG.info("Saved config for channel=%s: %s", viewer.channel_id, payload)
    return {"ok": True, "channel": viewer.channel_id}
