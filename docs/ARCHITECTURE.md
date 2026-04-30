# ASCIIMUD Architecture

## Data flow

```
                     +-----------------------------+
                     |  WoW Classic Era client     |
                     |                             |
                     |  +-----------------------+  |
                     |  |  ASCIIMUD addon       |  |
   Blizzard events -> |  EventBus -> State    |  |
                     |  |     |          |     |  |
                     |  |  Severity   Coalesce |  |
                     |  |     |          |     |  |
                     |  |  Render (Grid/Feed/  |  |
                     |  |   Header/Effects)    |  |  <-- you see this
                     |  |          |           |  |
                     |  |       Exporter       |  |
                     |  +----------|-----------+  |
                     +-------------|--------------+
                                   v
                       /chatlog -> Logs/WoWChatLog.txt
                                   |
                                   v
                     +-----------------------------+
                     |  companion.py (this PC)     |
                     |  tail -> StateStore -> Hub  |
                     |          |                  |
                     |          v                  |
                     |  WebSocket /ws              |
                     +--------------|--------------+
                                    v
                     +-----------------------------+
                     |  overlay/ (OBS Browser src) |
                     |  rich tactical UI for chat  |
                     +-----------------------------+
```

## Why through the chat log?

WoW addons cannot open sockets or write arbitrary files; they can only print
text. `/chatlog` is the one sanctioned way to get text out of the sandbox at
high frequency. The addon prefixes every machine line with `ASCIIMUD|` so the
companion can filter cleanly.

## Boundaries

| Concern                         | Lives in       |
| ------------------------------- | -------------- |
| What the player sees            | `addon/render` |
| What chat sees                  | `overlay/`     |
| Authoritative state             | `addon/core/State` then mirrored in `companion` |
| Severity / pacing               | `addon/systems/Severity` |
| Spam reduction                  | `addon/systems/Coalesce` |
| Wire format                     | `docs/EVENT_SCHEMA.md` |

## Phase B / C (not in this scaffold)

- **Twitch Extension + EBS** — chat-side interactivity. Will subscribe to the
  same WebSocket through a public relay.
- **LLM narrator + TTS** — consumes snapshots, produces prose for the feed
  and/or audio.
