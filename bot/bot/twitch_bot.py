"""twitchio wrapper.

The bot exposes a simple `say(message)` entry point that respects the global
cooldown + dedupe in `Cooldowns`. Commands are dispatched to handlers in
`commands.py` and routed through the same formatter used for auto-posts.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

import aiohttp
from twitchio.ext import commands as tio_commands

from .commands import COMMANDS
from .config import Config
from .cooldowns import Cooldowns
from .derived import Derived
from .formatter import maybe_rewrite, template

LOG = logging.getLogger("asciimud.bot.twitch")


class AsciiMudBot(tio_commands.Bot):
    def __init__(self, cfg: Config, derived: Derived, cooldowns: Cooldowns,
                 ai_session: aiohttp.ClientSession) -> None:
        super().__init__(
            token=cfg.bot_token,
            prefix="!",
            initial_channels=[cfg.channel],
            nick=cfg.bot_nick,
        )
        self.cfg = cfg
        self.derived = derived
        self.cooldowns = cooldowns
        self._ai_session = ai_session
        self._channel_obj = None
        self.chat_messages_seen: int = 0

    async def event_ready(self) -> None:
        LOG.info("Twitch bot connected as %s; channel=%s",
                 self.nick, self.cfg.channel)
        # Cache the channel object for direct sends.
        self._channel_obj = self.get_channel(self.cfg.channel)

    async def event_message(self, message) -> None:  # type: ignore[override]
        if message.echo:
            return
        self.chat_messages_seen += 1
        await self.handle_commands(message)

    # ---- public send (used by auto-posts and command replies) ----------
    async def say(self, kind: str, facts: dict, *, cooldown_key: str,
                  interval: float) -> bool:
        msg = template(kind, facts, prefix=self.cfg.prefix)
        msg = await maybe_rewrite(
            msg, kind, facts,
            enabled=self.cfg.ai_enabled,
            api_key=self.cfg.openai_api_key,
            model=self.cfg.openai_model,
            max_chars=self.cfg.ai_max_chars,
            timeout=self.cfg.ai_timeout_seconds,
            session=self._ai_session,
        )
        if not self.cooldowns.should_send(cooldown_key, interval, msg):
            LOG.debug("suppressed (cooldown/dedupe): key=%s", cooldown_key)
            return False
        ch = self._channel_obj or self.get_channel(self.cfg.channel)
        if ch is None:
            LOG.warning("No channel handle yet; dropping message")
            return False
        try:
            await ch.send(msg)
        except Exception as e:  # noqa: BLE001
            LOG.warning("send failed: %s", e)
            return False
        self.cooldowns.commit(cooldown_key, msg)
        LOG.info("posted: %s", msg)
        return True

    # ---------- command bindings ----------
    async def _dispatch(self, ctx, cmd_name: str) -> None:
        handler = COMMANDS.get(cmd_name)
        if handler is None:
            return
        kind, facts = handler(self.derived)
        # Per-user-per-command cooldown.
        key = f"cmd:{cmd_name}:{ctx.channel.name}"
        await self.say(kind, facts, cooldown_key=key,
                       interval=self.cfg.cooldowns.command_reply)

    @tio_commands.command(name="status")
    async def _status(self, ctx): await self._dispatch(ctx, "status")

    @tio_commands.command(name="rules")
    async def _rules(self, ctx): await self._dispatch(ctx, "rules")

    @tio_commands.command(name="danger")
    async def _danger(self, ctx): await self._dispatch(ctx, "danger")

    @tio_commands.command(name="objective")
    async def _objective(self, ctx): await self._dispatch(ctx, "objective")

    @tio_commands.command(name="stats")
    async def _stats(self, ctx): await self._dispatch(ctx, "stats")

    @tio_commands.command(name="closecalls")
    async def _closecalls(self, ctx): await self._dispatch(ctx, "closecalls")

    @tio_commands.command(name="deathlog")
    async def _deathlog(self, ctx): await self._dispatch(ctx, "deathlog")

    @tio_commands.command(name="help")
    async def _help(self, ctx): await self._dispatch(ctx, "help")

    @tio_commands.command(name="addon", aliases=["blind", "blindscreen", "textmode", "overlay"])
    async def _addon(self, ctx) -> None:
        if not self.cfg.addon_url:
            return
        kind, facts = ("addon", {"addonUrl": self.cfg.addon_url})
        key = f"cmd:addon:{ctx.channel.name}"
        await self.say(kind, facts, cooldown_key=key,
                       interval=self.cfg.cooldowns.command_reply)

    @tio_commands.command(name="map", aliases=["livemp", "livemap", "location", "where"])
    async def _map(self, ctx) -> None:
        if not self.cfg.map_url:
            return
        key = f"cmd:map:{ctx.channel.name}"
        await self.say("map", {"mapUrl": self.cfg.map_url}, cooldown_key=key,
                       interval=self.cfg.cooldowns.command_reply)

    @tio_commands.command(name="interface", aliases=["ui", "panel", "widgets", "hud"])
    async def _interface(self, ctx) -> None:
        if not self.cfg.interface_url:
            return
        key = f"cmd:interface:{ctx.channel.name}"
        await self.say("interface",
                       {"interfaceUrl": self.cfg.interface_url},
                       cooldown_key=key,
                       interval=self.cfg.cooldowns.command_reply)

    @tio_commands.command(name="setobjective")
    async def _setobjective(self, ctx, *, text: str = "") -> None:
        if (ctx.author.name or "").lower() != self.cfg.broadcaster_login:
            return
        if not text.strip():
            return
        kind, facts = self.derived.set_objective(text)
        await self.say(kind, facts,
                       cooldown_key="objective_changed", interval=0)
