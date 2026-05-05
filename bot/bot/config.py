"""Config loader: .env (secrets) + optional bot.toml (tunables).

Secrets MUST come from environment / .env — never from the toml file. The
toml is committed-friendly; .env is gitignored.
"""
from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

LOG = logging.getLogger("asciimud.bot.config")


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Cooldowns:
    generic_update: float = 300
    recap: float = 420
    danger_high: float = 60
    danger_critical: float = 25
    close_call: float = 60
    addon_disconnect: float = 30
    command_reply: float = 15
    global_between: float = 4
    dedupe_window: float = 90


@dataclass
class Config:
    # Twitch
    bot_nick: str = ""
    bot_token: str = ""
    channel: str = ""
    broadcaster_login: str = ""
    broadcaster_display: str = ""

    # Companion
    companion_ws_url: str = "ws://127.0.0.1:8765/ws"

    # AI
    ai_enabled: bool = False
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    ai_max_chars: int = 450
    ai_timeout_seconds: float = 4.0

    # Tunables
    cooldowns: Cooldowns = field(default_factory=Cooldowns)
    recap_ring_size: int = 12
    recap_post_max: int = 5
    counters_file: Path = Path("data/run_counters.json")
    prefix: str = "[ASCIIMUD] "

    # ASCIIMUD addon (the screen-blinding overlay) — link the bot can share
    addon_url: str = ""
    addon_promo_interval: float = 1500  # 25 min; 0 disables periodic promo

    # Live map page (served by the Cloudflare EBS worker)
    map_url: str = ""

    # Interactive widget interface page (served by the EBS worker)
    interface_url: str = ""

    # Logging
    log_level: str = "INFO"


def load(env_path: Path | None = None, toml_path: Path | None = None) -> Config:
    if load_dotenv is not None:
        load_dotenv(env_path) if env_path else load_dotenv()

    cfg = Config(
        bot_nick=os.getenv("TWITCH_BOT_NICK", "").strip(),
        bot_token=os.getenv("TWITCH_BOT_TOKEN", "").strip(),
        channel=os.getenv("TWITCH_CHANNEL", "").strip().lower(),
        broadcaster_login=os.getenv("TWITCH_BROADCASTER_LOGIN", "").strip().lower(),
        broadcaster_display=os.getenv("BROADCASTER_DISPLAY_NAME", "").strip(),
        companion_ws_url=os.getenv("COMPANION_WS_URL", "ws://127.0.0.1:8765/ws").strip(),
        ai_enabled=_truthy(os.getenv("AI_ENABLED")),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        ai_max_chars=int(os.getenv("AI_MAX_CHARS", "450") or 450),
        ai_timeout_seconds=float(os.getenv("AI_TIMEOUT_SECONDS", "4") or 4),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        addon_url=os.getenv("ADDON_URL", "").strip(),
        addon_promo_interval=float(os.getenv("ADDON_PROMO_INTERVAL", "1500") or 1500),
        map_url=os.getenv("MAP_URL", "").strip(),
        interface_url=os.getenv("INTERFACE_URL", "").strip(),
    )

    if toml_path and toml_path.exists():
        try:
            data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as e:
            LOG.warning("config toml parse failed: %s", e)
            data = {}
        c = data.get("cooldowns", {})
        for k, v in c.items():
            if hasattr(cfg.cooldowns, k):
                setattr(cfg.cooldowns, k, float(v))
        r = data.get("recap", {})
        cfg.recap_ring_size = int(r.get("ring_size", cfg.recap_ring_size))
        cfg.recap_post_max = int(r.get("post_max", cfg.recap_post_max))
        cnt = data.get("counters", {})
        if "file" in cnt:
            cfg.counters_file = Path(cnt["file"])
        n = data.get("narration", {})
        if "prefix" in n:
            cfg.prefix = str(n["prefix"])

    if not cfg.ai_enabled:
        cfg.openai_api_key = ""

    return cfg


def validate_for_runtime(cfg: Config) -> list[str]:
    """Return a list of human-readable problems blocking startup."""
    problems: list[str] = []
    if not cfg.bot_nick:
        problems.append("TWITCH_BOT_NICK is empty")
    if not cfg.bot_token:
        problems.append("TWITCH_BOT_TOKEN is empty")
    elif not cfg.bot_token.startswith("oauth:"):
        problems.append("TWITCH_BOT_TOKEN must start with 'oauth:'")
    if not cfg.channel:
        problems.append("TWITCH_CHANNEL is empty")
    if not cfg.broadcaster_login:
        problems.append("TWITCH_BROADCASTER_LOGIN is empty")
    return problems
