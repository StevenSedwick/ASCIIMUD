# ASCIIMUD Twitch Chat Bot

Local Python bot that reads the ASCIIMUD companion's WebSocket stream and
narrates the run in Twitch chat. Runs alongside the existing OBS overlay and
EBS forwarder. Touches no game files.

## Architecture

```
ASCIIMUD addon (in WoW)
   → companion.py ──ws──→ ┌─ overlay (OBS)
                          ├─ EBS (Twitch Extension)
                          └─ THIS BOT  ──IRC──→ Twitch chat
```

The bot subscribes to `ws://127.0.0.1:8765/ws`. It synthesizes the events the
addon doesn't emit (level-up, close-call, target/zone change, addon
disconnect/reconnect) by diffing snapshots, and it maintains run counters
in-memory + `data/run_counters.json`.

## Setup (Windows, PowerShell)

```powershell
cd C:\Users\kayla\dev\ASCIIMUD\bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env       # then edit .env
Copy-Item config.example.toml bot.toml   # optional; defaults are fine
```

Required environment variables (in `.env`):

| Var | Purpose |
|---|---|
| `TWITCH_BOT_NICK` | Login of a SEPARATE bot account (not the broadcaster). |
| `TWITCH_BOT_TOKEN` | OAuth token starting with `oauth:` (https://twitchapps.com/tmi/). |
| `TWITCH_CHANNEL` | Channel login to join (lowercase). |
| `TWITCH_BROADCASTER_LOGIN` | Owner login (lowercase) — gates `!setobjective`. |
| `BROADCASTER_DISPLAY_NAME` | Name to use in narration ("the player"). |
| `COMPANION_WS_URL` | Defaults to `ws://127.0.0.1:8765/ws`. |
| `AI_ENABLED` | `false` (default) disables the AI rewriter entirely. |
| `OPENAI_API_KEY` | Required only if `AI_ENABLED=true`. |

## Run

```powershell
python run.py
# or
python -m bot
```

The bot starts, posts a one-shot intro line to chat, then listens for events
and viewer commands. Logs go to stdout at `LOG_LEVEL` (default INFO).

## Local test (no Twitch needed)

Run the unit tests from the `bot/` folder:

```powershell
python -m pytest tests -q
```

To dry-run end-to-end without Twitch credentials, point the bot at a fake
companion WebSocket and stub the Twitch send. The simplest path is the unit
tests above — they exercise `Derived`, `Cooldowns`, and `formatter` (which
together cover all message-shaping logic). Integration with `twitchio` is a
thin wrapper.

To produce live data into the bot without going on-air:

1. Start the companion (`python companion.py` in `companion/`).
2. Stand up a private Twitch test channel, set `TWITCH_CHANNEL` to it,
   and join it from a second browser as a viewer to issue commands.
3. The bot will only post in that channel.

## In-game test checklist

With WoW + ASCIIMUD addon + companion + bot all running in your test channel:

- [ ] On startup the bot posts the `stream_start` intro line.
- [ ] `!help` lists the v1 commands.
- [ ] `!status` reports level, class, HP%, zone (resolved by name not hash),
      combat state, danger level, and a last event.
- [ ] `!rules` posts the challenge explanation.
- [ ] `!danger` reflects the current synthesized danger level.
- [ ] Take HP below 25% and recover above 50% → `!closecalls` increments and
      a `close_call` line is auto-posted (cooldown 60 s).
- [ ] Cross a zone border → bot auto-posts `zone change` line shortly after.
- [ ] Level up → bot auto-posts the level-up line and `!status` shows the new
      level.
- [ ] `/asciimud reload` (or stop the companion) → after ~12 s the bot posts
      `addon_disconnected`. Restart the companion → `addon_reconnected`.
- [ ] As broadcaster: `!setobjective Reach Goldshire` → bot auto-posts the
      objective-update line and `!objective` reflects it.
- [ ] Disable AI (`AI_ENABLED=false`) → bot still posts deterministic
      template messages.

## Security

- Secrets only via `.env` (gitignored). No token or key is logged.
- Use a separate Twitch account for the bot. The broadcaster account is not
  required.
- AI rewriter is opt-in. If the AI returns a message that introduces a
  number not in the source facts, the deterministic template is used instead.

## Files changed / added

This bot lives entirely in `C:\Users\kayla\dev\ASCIIMUD\bot\`. No files in
the addon, companion, overlay, EBS, or extension are modified.

## Risks / assumptions

- Companion-WS is the single source of truth. If the screen-grid pipeline
  stalls (e.g. window minimised so screenshots break), the bot will report
  `addon_disconnected` after 12 s of snapshot silence.
- Player name is taken from `BROADCASTER_DISPLAY_NAME`; the snapshot does
  not currently carry it. (Cheap to add to the grid later — there's pixel
  budget for it.)
- `objective` is broadcaster-set via chat; the addon does not yet emit one.
- Counters are per-machine, not per-character. Edit `data/run_counters.json`
  to reset, or delete the file.
