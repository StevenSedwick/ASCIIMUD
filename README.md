# ASCIIMUD

A **headless event-streaming pipeline** for **World of Warcraft Classic Era**.

ASCIIMUD observes your character and emits structured NDJSON events that drive
an OBS browser-source overlay (and, in Phase B, a Twitch Extension) — giving
your chat viewers a richer tactical view than you see yourself.

The in-game UI for the player is owned by a separate addon
(**TextAdventurer**); ASCIIMUD draws nothing on screen — it only listens and
exports.

## Components

| Path         | Purpose                                                          |
| ------------ | ---------------------------------------------------------------- |
| `addon/`     | Headless WoW addon. Hooks events, writes NDJSON to chat log.     |
| `companion/` | Python process that tails `WoWChatLog.txt` and runs a WS server. |
| `overlay/`   | OBS browser-source UI that consumes the WS stream.               |
| `ebs/`       | (Phase B) Cloud EBS for the Twitch Extension.                    |
| `extension/` | (Phase B) Twitch Extension viewer/config/live panels.            |
| `docs/`      | Architecture, setup, event schema.                               |

## Quick start

See [`docs/SETUP.md`](docs/SETUP.md).

## Roadmap

- **Phase A** *(current)* — headless addon + companion + OBS overlay.
- **Phase B** *(scaffolded)* — Twitch Extension + EBS for in-stream interactivity.
- **Phase C** — Optional LLM narrator + TTS.

## License

TBD.
