# ASCIIMUD

A tactical ASCII MUD overlay for **World of Warcraft Classic Era**.

ASCIIMUD replaces the default WoW UI with a full-screen text interface — an ASCII
tactical grid, a scrolling event feed, and severity-driven effects — and streams
the same world state out to an OBS browser source so chat sees a richer view than
you do.

## Components

| Path         | Purpose                                                          |
| ------------ | ---------------------------------------------------------------- |
| `addon/`     | The in-game WoW addon. Drop into `Interface/AddOns/ASCIIMUD`.   |
| `companion/` | Python process that tails `WoWChatLog.txt` and runs a WS server. |
| `overlay/`   | OBS browser-source UI that consumes the WS stream.               |
| `docs/`      | Architecture, setup, event schema.                               |

## Quick start

See [`docs/SETUP.md`](docs/SETUP.md).

## Roadmap

- **Phase A** *(this scaffold)* — addon + companion + OBS overlay.
- **Phase B** — Twitch Extension + EBS for in-stream interactivity.
- **Phase C** — Optional LLM narrator + TTS.

## License

TBD.
