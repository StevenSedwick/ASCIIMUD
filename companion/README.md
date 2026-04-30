# ASCIIMUD Companion

Tails `WoWChatLog.txt`, parses NDJSON events emitted by the addon, and
broadcasts them to any connected WebSocket clients (the OBS overlay).

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy config.example.toml config.toml
# edit config.toml so log_path points at your WoWChatLog.txt
python companion.py
```

The server listens on `ws://127.0.0.1:8765/ws` by default.

## Notes

- Requires Python 3.11+ (uses `tomllib`).
- The addon enables `/chatlog` automatically on first login. If your log file
  doesn't appear, type `/chatlog` in-game once.
- See [`../docs/EVENT_SCHEMA.md`](../docs/EVENT_SCHEMA.md) for the wire format.
