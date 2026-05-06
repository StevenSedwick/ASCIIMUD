"""Message formatting.

`format(event_kind, facts)` always returns a deterministic template message.
If AI is enabled, we additionally try to rewrite the template using the AI
provider; the template is used as a fallback whenever the AI call fails,
exceeds AI_MAX_CHARS, returns empty, or returns content that introduces facts
not present in `facts`.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from .narration import fmt_secs, hp_phrase
from .zones import name as zone_name

LOG = logging.getLogger("asciimud.bot.formatter")

PREFIX = "[ASCIIMUD] "

CHALLENGE_LINE = (
    "ASCIIMUD rules: WoW Classic Hardcore through text output. "
    "Normal game view hidden/minimized. The addon is the player's eyes."
)


def _t(prefix: str, body: str) -> str:
    return prefix + body


def _facts_get(facts: dict, *path, default=None):
    cur: Any = facts
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur if cur is not None else default


def template(kind: str, facts: dict, prefix: str = PREFIX) -> str:
    """Deterministic template; never raises."""
    f = facts or {}
    z = zone_name(_facts_get(f, "zoneHash"))
    hp = _facts_get(f, "hpPct")
    lvl = _facts_get(f, "level")
    cls = _facts_get(f, "class") or "?"
    target = _facts_get(f, "targetName") or "—"
    target_lvl = _facts_get(f, "targetLevel")
    danger = _facts_get(f, "dangerLevel") or "none"
    objective = _facts_get(f, "objective") or "no objective set"
    last = _facts_get(f, "lastEvent") or "—"
    name = _facts_get(f, "playerName") or "the player"

    if kind == "stream_start":
        return _t(prefix,
            "The world is hidden. The text is all we have. "
            "Welcome to a WoW Classic Hardcore run played through the Text Adventure addon!")
    if kind == "rules":
        return _t(prefix, CHALLENGE_LINE)
    if kind == "addon":
        url = _facts_get(f, "addonUrl") or ""
        if not url:
            return _t(prefix, "Addon link not configured.")
        return _t(prefix,
            f"The blank-screen overlay you're seeing is the Text Adventure "
            f"addon for WoW Classic: {url}")
    if kind == "addon_promo":
        url = _facts_get(f, "addonUrl") or ""
        if not url:
            return _t(prefix, "Addon link not configured.")
        return _t(prefix,
            f"If the blank-screen overlay is new to you — this is the "
            f"addon making it possible: {url}")
    if kind == "map":
        url = _facts_get(f, "mapUrl") or ""
        if not url:
            return _t(prefix, "Live map not configured.")
        return _t(prefix, f"Live map (updates every 2s): {url}")
    if kind == "interface":
        url = _facts_get(f, "interfaceUrl") or ""
        if not url:
            return _t(prefix, "Interface page not configured.")
        return _t(prefix,
            f"Drag-and-drop live interface (vitals, target, buffs, action bar, "
            f"map): {url}")
    if kind == "help":
        cmds = ("!status !rules !danger !objective !stats "
                "!closecalls !deathlog !addon !map !interface !help")
        return _t(prefix, "Commands: " + cmds)
    if kind == "status":
        return _t(prefix,
            f"Level {lvl} {cls} | {hp_phrase(hp)} | zone: {z} | "
            f"combat: {'yes' if _facts_get(f, 'inCombat') else 'no'} | "
            f"danger: {danger} | last: {last}")
    if kind == "danger":
        reasons = _facts_get(f, "dangerReasons") or []
        rtxt = "; ".join(reasons) if reasons else "no specific threats reported"
        return _t(prefix, f"Danger {danger}. {rtxt}.")
    if kind == "objective":
        changed = _facts_get(f, "objectiveChangedAgo")
        suffix = f" (set {fmt_secs(changed)} ago)" if changed is not None else ""
        return _t(prefix, f"Objective: {objective}{suffix}.")
    if kind == "stats":
        return _t(prefix,
            f"{name}: alive {fmt_secs(_facts_get(f, 'timeAlive', default=0))}, "
            f"level {lvl}, kills {_facts_get(f, 'killCount', default=0)}, "
            f"close calls {_facts_get(f, 'closeCallCount', default=0)}, "
            f"deaths {_facts_get(f, 'deathCount', default=0)}.")
    if kind == "closecalls":
        n = _facts_get(f, "closeCallCount", default=0)
        last_cc = _facts_get(f, "lastCloseCall")
        if not n:
            return _t(prefix, "No close calls logged this run.")
        tail = f" Latest: {last_cc}." if last_cc else ""
        return _t(prefix, f"Close calls: {n}.{tail}")
    if kind == "deathlog":
        last_death = _facts_get(f, "lastDeath")
        if not last_death:
            return _t(prefix, "The current run is still alive.")
        return _t(prefix, f"Latest death: {last_death}.")
    if kind == "level_up":
        return _t(prefix, f"Level up. Now level {lvl} {cls} in {z}.")
    if kind == "objective_changed":
        return _t(prefix, f"Objective updated: {objective}.")
    if kind == "danger_changed":
        return _t(prefix,
            f"Danger {danger}: {hp_phrase(hp)}, "
            f"{'in combat' if _facts_get(f, 'inCombat') else 'out of combat'}, "
            f"target {target}{f' (lvl {target_lvl})' if target_lvl else ''}.")
    if kind == "close_call":
        low = _facts_get(f, "lowestHpPct", default=hp or 0)
        return _t(prefix,
            f"Close call logged: HP dropped to {int(low)}%. The run survived.")
    if kind == "death":
        return _t(prefix, f"Death recorded. {name} fell in {z} at level {lvl}.")
    if kind == "addon_disconnected":
        return _t(prefix, "Addon stream lost. Telemetry paused.")
    if kind == "addon_reconnected":
        return _t(prefix, "Addon stream restored. Telemetry resumed.")
    if kind == "entered_combat":
        return _t(prefix, f"Combat: engaged {target}"
                          f"{f' (lvl {target_lvl})' if target_lvl else ''}.")
    if kind == "left_combat":
        return _t(prefix, f"Combat ended. {hp_phrase(hp)}.")
    if kind == "target_changed":
        if not target or target == "—":
            return _t(prefix, "Target cleared.")
        return _t(prefix, f"New target: {target}"
                          f"{f' (lvl {target_lvl})' if target_lvl else ''}.")
    if kind == "zone_changed":
        return _t(prefix, f"Zone change: now in {z}.")
    return _t(prefix, f"{kind}: {json.dumps(f, separators=(',', ':'))[:200]}")


# --------------------- AI rewriter (optional) ---------------------------------

_AI_SYSTEM = (
    "You rewrite a single short broadcast line for a Twitch chat bot. "
    "TONE: calm survival narrator / black-box recorder. "
    "STRICT RULES: (1) you may ONLY use facts present in the provided JSON; "
    "(2) you must NOT invent names, numbers, locations, spells, mobs, or "
    "outcomes; (3) keep the [ASCIIMUD] prefix; (4) one line, <= {max} chars; "
    "(5) safe for Twitch chat (no slurs, no @everyone-style spam, no links); "
    "(6) if facts are insufficient, return the draft unchanged."
)


async def maybe_rewrite(template_msg: str, kind: str, facts: dict, *,
                        enabled: bool, api_key: str, model: str,
                        max_chars: int, timeout: float,
                        session: aiohttp.ClientSession | None = None) -> str:
    if not enabled or not api_key:
        return template_msg
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _AI_SYSTEM.format(max=max_chars)},
            {"role": "user", "content": json.dumps(
                {"kind": kind, "facts": facts, "draft": template_msg},
                separators=(",", ":"))},
        ],
        "max_tokens": 200,
        "temperature": 0.4,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    own_session = session is None
    sess = session or aiohttp.ClientSession()
    try:
        async with sess.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload, headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            if resp.status != 200:
                LOG.info("AI rewrite skipped: HTTP %s", resp.status)
                return template_msg
            data = await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        LOG.info("AI rewrite failed: %s — using template", e)
        return template_msg
    finally:
        if own_session:
            await sess.close()

    try:
        text = (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        return template_msg

    if not text or len(text) > max_chars:
        return template_msg
    if not text.startswith("[ASCIIMUD]"):
        # Re-prefix; AI is not allowed to drop the brand.
        text = "[ASCIIMUD] " + text
        if len(text) > max_chars:
            return template_msg
    if _hallucinates(text, facts):
        LOG.info("AI rewrite hallucinated facts; using template. AI=%r", text)
        return template_msg
    return text


# A loose, pragmatic guard: if the AI mentions a number not in facts, we
# reject it. Numbers are the easiest hallucination to detect; names are too
# fuzzy to police automatically.
import re

_NUM_RE = re.compile(r"\b\d+\b")


def _hallucinates(text: str, facts: dict) -> bool:
    fact_nums: set[str] = set()

    def walk(v: Any) -> None:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            fact_nums.add(str(int(v)))
        elif isinstance(v, str):
            for n in _NUM_RE.findall(v):
                fact_nums.add(n)
        elif isinstance(v, dict):
            for vv in v.values():
                walk(vv)
        elif isinstance(v, (list, tuple)):
            for vv in v:
                walk(vv)

    walk(facts)
    for n in _NUM_RE.findall(text):
        if n not in fact_nums:
            return True
    return False
