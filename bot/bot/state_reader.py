"""Subscribe to the companion WebSocket. Reconnect with backoff."""
from __future__ import annotations

import asyncio
import json
import logging

import aiohttp

LOG = logging.getLogger("asciimud.bot.state")


class StateReader:
    def __init__(self, url: str, on_event, on_open, on_close,
                 stop: asyncio.Event) -> None:
        self.url = url
        self._on_event = on_event
        self._on_open = on_open
        self._on_close = on_close
        self._stop = stop

    async def run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(
                        self.url,
                        heartbeat=20,
                        timeout=aiohttp.ClientWSTimeout(ws_close=10),
                    ) as ws:
                        backoff = 1.0
                        await self._on_open()
                        async for msg in ws:
                            if self._stop.is_set():
                                break
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                try:
                                    data = json.loads(msg.data)
                                except json.JSONDecodeError:
                                    continue
                                if isinstance(data, dict) and "t" in data:
                                    await self._on_event(data)
                            elif msg.type in (aiohttp.WSMsgType.CLOSED,
                                              aiohttp.WSMsgType.ERROR):
                                break
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
                LOG.info("WS connect/read error: %s", e)
            except Exception as e:  # noqa: BLE001
                LOG.exception("WS unexpected error: %s", e)
            finally:
                await self._on_close()
            if self._stop.is_set():
                return
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                return
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, 30.0)
