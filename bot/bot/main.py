"""Asyncio orchestrator.

Wires StateReader → Derived → AsciiMudBot, plus a periodic recap ticker and
counter persistence on shutdown.
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

import aiohttp

from .config import Config, load, validate_for_runtime
from .cooldowns import Cooldowns
from .derived import Counters, Derived
from .rules import decide
from .state_reader import StateReader
from .twitch_bot import AsciiMudBot

LOG = logging.getLogger("asciimud.bot")


async def _amain(cfg: Config) -> int:
    counters = Counters.load(cfg.counters_file)
    derived = Derived(cfg.broadcaster_display,
                      recap_ring_size=cfg.recap_ring_size,
                      counters=counters)
    cd = Cooldowns(global_min_interval=cfg.cooldowns.global_between,
                   dedupe_window=cfg.cooldowns.dedupe_window)

    stop = asyncio.Event()

    def _signal(_sig, _frm):
        stop.set()
    try:
        signal.signal(signal.SIGINT, _signal)
        signal.signal(signal.SIGTERM, _signal)
    except (ValueError, AttributeError):
        pass

    ai_session = aiohttp.ClientSession()
    bot = AsciiMudBot(cfg, derived, cd, ai_session)

    async def dispatch_events(events):
        for kind, facts in events:
            d = decide(kind, facts, cfg.cooldowns)
            if d.post:
                await bot.say(d.kind, d.facts or {}, cooldown_key=d.key,
                              interval=d.interval)

    async def on_event(evt: dict) -> None:
        await dispatch_events(derived.feed(evt))

    async def on_open() -> None:
        await dispatch_events(derived.on_ws_open())

    async def on_close() -> None:
        await dispatch_events(derived.on_ws_closed())

    reader = StateReader(cfg.companion_ws_url, on_event, on_open, on_close, stop)

    async def ticker() -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=10.0)
                return
            except asyncio.TimeoutError:
                pass
            await dispatch_events(derived.tick())

    async def recap_ticker() -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=cfg.cooldowns.recap)
                return
            except asyncio.TimeoutError:
                pass
            await dispatch_events([("recap_tick", derived.recap_facts(
                max_items=cfg.recap_post_max))])

    async def addon_promo_ticker() -> None:
        if not cfg.addon_url or cfg.addon_promo_interval <= 0:
            return
        last_seen = 0
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=cfg.addon_promo_interval)
                return
            except asyncio.TimeoutError:
                pass
            seen = bot.chat_messages_seen
            if seen <= last_seen:
                continue  # dead chat — skip this round
            last_seen = seen
            await bot.say(
                "addon_promo", {"addonUrl": cfg.addon_url},
                cooldown_key="addon_promo",
                interval=cfg.addon_promo_interval,
            )

    async def stop_bot_when_done() -> None:
        await stop.wait()
        await bot.close()

    # Post stream_start once at boot (via the same dispatch path).
    async def stream_start() -> None:
        await asyncio.sleep(2)
        await dispatch_events([("stream_start", derived.snapshot_facts())])

    try:
        await asyncio.gather(
            bot.start(),
            reader.run(),
            ticker(),
            recap_ticker(),
            addon_promo_ticker(),
            stop_bot_when_done(),
            stream_start(),
            return_exceptions=True,
        )
    finally:
        try:
            derived.counters.save(cfg.counters_file)
        finally:
            await ai_session.close()
    return 0


def run() -> None:
    cfg = load(toml_path=Path("bot.toml"))
    logging.basicConfig(
        level=getattr(logging, cfg.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    problems = validate_for_runtime(cfg)
    if problems:
        for p in problems:
            print(f"config error: {p}", file=sys.stderr)
        print("Refusing to start. See bot/.env.example for required values.",
              file=sys.stderr)
        sys.exit(2)
    try:
        sys.exit(asyncio.run(_amain(cfg)))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
