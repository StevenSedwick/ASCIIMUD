"""ASCIIMUD companion test suite.

Tests are split into three layers:

  Unit         — pure logic, no I/O, no async, no imports from aiohttp
  Integration  — async tests using aiohttp.test_utils or real WS connections
  E2E          — runs the mock + companion + asserts messages arrive on WS

Run all:
    cd companion && pip install -r requirements.txt && pip install pytest pytest-asyncio
    pytest ../tests/ -v

Run only unit:
    pytest ../tests/ -v -m unit
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Make the companion module importable from repo root or tests/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "companion"))

import companion  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PREFIX = "ASCIIMUD~"

def make_snapshot(hp=320, hpMax=360, mp=180, mpMax=200, level=12,
                  zone_name="Elwynn Forest", sev=0, combat=False,
                  target=None, tick=1):
    return {
        "t": "snapshot",
        "data": {
            "v": 1, "tick": tick, "combat": combat, "chapter": 1,
            "player": {"name": "Testwick", "class": "WARLOCK", "level": level,
                       "hp": hp, "hpMax": hpMax, "mp": mp, "mpMax": mpMax},
            "zone": {"name": zone_name, "subzone": "", "x": 0, "y": 0},
            "target": target,
        }
    }


def make_line(obj: dict) -> str:
    """Format a dict the way the addon writes it to WoWChatLog.txt."""
    # WoW prefixes each chat line with a timestamp bracket; the companion
    # searches for PREFIX anywhere on the line.
    ts = "4/30 12:00:00.000"
    return f"{ts}  CHAT_MSG_SAY,{PREFIX}{json.dumps(obj)}"


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestStateStore:
    def test_init_empty(self):
        s = companion.StateStore()
        assert s.snapshot == {}
        assert s.severity == 0

    def test_apply_snapshot(self):
        s = companion.StateStore()
        snap = make_snapshot()
        s.apply(snap)
        assert s.snapshot == snap["data"]

    def test_apply_severity(self):
        s = companion.StateStore()
        s.apply({"t": "severity", "level": 3})
        assert s.severity == 3

    def test_apply_severity_clamps_type(self):
        s = companion.StateStore()
        s.apply({"t": "severity", "level": "5"})  # string "5"
        assert s.severity == 5

    def test_apply_ignores_unknown_type(self):
        s = companion.StateStore()
        s.apply({"t": "unknown_future_event", "data": {}})
        assert s.snapshot == {}

    def test_apply_multiple(self):
        s = companion.StateStore()
        s.apply(make_snapshot(hp=100))
        s.apply({"t": "severity", "level": 4})
        s.apply(make_snapshot(hp=50))
        assert s.snapshot["player"]["hp"] == 50
        assert s.severity == 4


class TestIngestLine:
    """Tests for companion.ingest() — the chat-line parser."""

    @pytest.mark.asyncio
    async def test_valid_snapshot_updates_store(self):
        store = companion.StateStore()
        hub = companion.Hub()
        snap = make_snapshot(hp=200)
        line = make_line(snap)
        await companion.ingest(line, store, hub, None)
        assert store.snapshot["player"]["hp"] == 200

    @pytest.mark.asyncio
    async def test_valid_severity_updates_store(self):
        store = companion.StateStore()
        hub = companion.Hub()
        line = make_line({"t": "severity", "level": 3})
        await companion.ingest(line, store, hub, None)
        assert store.severity == 3

    @pytest.mark.asyncio
    async def test_line_without_prefix_ignored(self):
        store = companion.StateStore()
        hub = companion.Hub()
        line = "4/30 12:00:00.000  CHAT_MSG_SAY,Onyxia is up!"
        await companion.ingest(line, store, hub, None)
        assert store.snapshot == {}

    @pytest.mark.asyncio
    async def test_malformed_json_ignored(self):
        store = companion.StateStore()
        hub = companion.Hub()
        line = "4/30  " + PREFIX + "{ not valid json }"
        await companion.ingest(line, store, hub, None)
        assert store.snapshot == {}

    @pytest.mark.asyncio
    async def test_prefix_in_middle_of_line(self):
        store = companion.StateStore()
        hub = companion.Hub()
        snap = make_snapshot(hp=111)
        line = "timestamp CHAT_MSG_SAY Testwick: " + PREFIX + json.dumps(snap)
        await companion.ingest(line, store, hub, None)
        assert store.snapshot["player"]["hp"] == 111

    @pytest.mark.asyncio
    async def test_hub_receives_broadcast(self):
        store = companion.StateStore()
        hub = companion.Hub()
        received = []

        class FakeWS:
            async def send_str(self, msg):
                received.append(json.loads(msg))

        ws = FakeWS()
        hub.clients.add(ws)  # type: ignore[arg-type]
        line = make_line({"t": "severity", "level": 5})
        await companion.ingest(line, store, hub, None)
        assert len(received) == 1
        assert received[0]["t"] == "severity"
        assert received[0]["level"] == 5

    @pytest.mark.asyncio
    async def test_ebs_forwarder_receives_raw_json(self):
        store = companion.StateStore()
        hub = companion.Hub()
        submitted = []

        class FakeEBS:
            async def submit(self, raw):
                submitted.append(raw)

        snap = make_snapshot(hp=99)
        line = make_line(snap)
        await companion.ingest(line, store, hub, FakeEBS())  # type: ignore[arg-type]
        assert len(submitted) == 1
        parsed = json.loads(submitted[0])
        assert parsed["t"] == "snapshot"


class TestHub:
    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_clients(self):
        hub = companion.Hub()
        dead_calls = 0

        class DeadWS:
            async def send_str(self, _msg):
                nonlocal dead_calls
                dead_calls += 1
                raise ConnectionResetError("gone")

        ws = DeadWS()
        hub.clients.add(ws)  # type: ignore[arg-type]
        await hub.broadcast({"t": "test"})
        assert ws not in hub.clients

    @pytest.mark.asyncio
    async def test_broadcast_empty_hub_is_noop(self):
        hub = companion.Hub()
        await hub.broadcast({"t": "test"})  # should not raise


class TestTokenBucketRateLimit:
    def test_initial_take(self):
        from companion import Hub  # Just a sanity check on imports
        # TokenBucket is in ratelimit.py for EBS, but companion itself doesn't
        # have one — this test just ensures the companion imports cleanly.
        assert companion.StateStore is not None

    def test_ingest_is_async_callable(self):
        import inspect
        assert inspect.iscoroutinefunction(companion.ingest)


# ---------------------------------------------------------------------------
# Integration — tail() + ingest() pipeline
# ---------------------------------------------------------------------------

class TestTailPipeline:
    @pytest.mark.asyncio
    async def test_tail_reads_new_lines(self, tmp_path):
        """Write to a file after tail starts; assert lines are consumed."""
        log = tmp_path / "WoWChatLog.txt"
        log.write_text("", encoding="utf-8")

        collected = []

        async def on_line(line):
            collected.append(line)

        async def write_then_stop():
            await asyncio.sleep(0.1)  # let tail get to the blocking read
            with log.open("a", encoding="utf-8") as f:
                snap = make_snapshot(hp=77)
                f.write(make_line(snap) + "\n")
                f.write(make_line({"t": "severity", "level": 2}) + "\n")
            await asyncio.sleep(0.3)
            task.cancel()

        task = asyncio.create_task(companion.tail(log, on_line))
        await write_then_stop()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(collected) >= 2
        assert any(PREFIX in l for l in collected)

    @pytest.mark.asyncio
    async def test_tail_waits_for_file_to_exist(self, tmp_path):
        """tail() retries until the file appears, then reads new lines from EOF.

        Sequence:
          t=0.00  tail starts (file missing), logs warning, sleeps 2s
          t=0.05  we create an EMPTY file (tail will find it after its sleep)
          t=2.3   tail wakes up, opens the now-existing file, seeks to EOF
          t=2.4   we write a line — tail picks it up in its next 0.1s poll
        """
        log = tmp_path / "missing.txt"
        collected = []

        async def on_line(line):
            collected.append(line)

        task = asyncio.create_task(companion.tail(log, on_line))
        await asyncio.sleep(0.05)
        log.write_text("", encoding="utf-8")  # create empty — tail finds it after retry

        # Wait for tail to open the file and seek to EOF (2s retry + margin).
        await asyncio.sleep(2.3)

        # Now write new content — tail will catch it in the next poll cycle.
        with log.open("a", encoding="utf-8") as f:
            f.write(make_line(make_snapshot(hp=42)) + "\n")

        await asyncio.sleep(0.5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert any(PREFIX in l for l in collected)


# ---------------------------------------------------------------------------
# E2E — companion WS server + mock log writer + real WS client
# ---------------------------------------------------------------------------

class TestCompanionE2E:
    @pytest.mark.asyncio
    async def test_snapshot_reaches_ws_client(self, tmp_path, unused_tcp_port):
        """Full pipeline: file write -> tail -> ingest -> Hub -> WS client."""
        import aiohttp

        log = tmp_path / "WoWChatLog.txt"
        log.write_text("", encoding="utf-8")

        cfg = {
            "wow":    {"log_path": str(log)},
            "server": {"host": "127.0.0.1", "port": unused_tcp_port},
        }

        # Patch load_config so we don't need a real config.toml.
        with patch.object(companion, "load_config", return_value=cfg):
            server_task = asyncio.create_task(_run_companion_server(cfg))
            await asyncio.sleep(0.5)  # give the server a moment to bind

            received = []
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    f"ws://127.0.0.1:{unused_tcp_port}/ws"
                ) as ws:
                    # Write a snapshot to the log — give tail time to poll.
                    await asyncio.sleep(0.2)
                    with log.open("a", encoding="utf-8") as f:
                        snap = make_snapshot(hp=222)
                        f.write(make_line(snap) + "\n")
                    # Drain messages until we see a snapshot or timeout.
                    deadline = asyncio.get_event_loop().time() + 4.0
                    while asyncio.get_event_loop().time() < deadline:
                        try:
                            msg = await asyncio.wait_for(ws.receive(), timeout=1.0)
                            if msg.type.name in ("TEXT", "BINARY"):
                                received.append(json.loads(msg.data))
                            if any(m.get("t") == "snapshot" for m in received):
                                break
                        except asyncio.TimeoutError:
                            pass
                    await ws.close()

            server_task.cancel()
            with pytest.raises((asyncio.CancelledError, Exception)):
                await server_task

        assert any(m.get("t") == "snapshot" for m in received)
        hp_values = [m["data"]["player"]["hp"]
                     for m in received if m.get("t") == "snapshot"]
        assert 222 in hp_values


async def _run_companion_server(cfg: dict) -> None:
    """Thin async wrapper to spin up the companion's aiohttp server."""
    from pathlib import Path
    store = companion.StateStore()
    hub = companion.Hub()
    log_path = Path(cfg["wow"]["log_path"])
    host = cfg["server"].get("host", "127.0.0.1")
    port = int(cfg["server"].get("port", 8765))

    from aiohttp import web
    app = web.Application()
    app["store"] = store
    app["hub"] = hub
    app.router.add_get("/ws", companion.ws_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    await companion.tail(log_path, lambda l: companion.ingest(l, store, hub, None))


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def unused_tcp_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
