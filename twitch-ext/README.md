# ASCIIMUD — Twitch Video-Overlay Extension

This is the **viewer-facing** half of the ASCIIMUD pipeline. It runs as a
Twitch [video overlay](https://dev.twitch.tv/docs/extensions/) on top of the
broadcaster's stream, connects to the Cloudflare Workers EBS over WebSocket,
and renders the same theatrical UI as the OBS overlay (`overlay/`).

## Files

| File         | Purpose                                                          |
| ------------ | ---------------------------------------------------------------- |
| `viewer.html`/`viewer.js`/`viewer.css` | Video overlay shown to viewers.   |
| `config.html`/`config.js`/`config.css` | Broadcaster config — sets EBS URL.|
| `app.js`     | Shared rendering engine (copy of `overlay/app.js`, deferred boot).|
| `icons.js`   | Spell glyph tables (copy of `overlay/icons.js`).                 |
| `style.css`  | Theatrical UI styles (copy of `overlay/style.css`).              |
| `build.ps1`  | Produces a Twitch-spec submission zip.                           |

## How it connects

1. Broadcaster opens the **Configuration View** in their Twitch dashboard,
   pastes the public URL of their Cloudflare Worker (e.g.
   `https://asciimud-ebs.<subdomain>.workers.dev`), and hits **Save**.
2. The setting is stored in Twitch's broadcaster configuration segment.
3. When a viewer loads the channel, `viewer.js` waits for
   `Twitch.ext.onAuthorized` (which gives `channelId` + a signed JWT), reads
   the EBS URL from configuration, and connects to
   `wss://<ebs-host>/ws/<channelId>?jwt=<token>`.
4. The Worker verifies the JWT (HS256 with the Twitch shared secret), accepts
   the WebSocket, and replays the latest snapshot + spell metadata.

## Toggle button

`viewer.js` adds a small circular button in the bottom-right corner. Clicking
it toggles `body.tx-collapsed` ↔ `body.tx-expanded`; the choice is persisted
to `localStorage` so each viewer's preference sticks.

## Local development

The extension is plain static HTML/JS — no bundler. To smoke-test outside of
Twitch:

```pwsh
cd twitch-ext
# any static file server works; from the repo root:
python -m http.server 8123 --directory .
# then open http://localhost:8123/viewer.html?ws=ws://127.0.0.1:8765/ws
```

The `?ws=` query param overrides the EBS URL when the Twitch helper isn't
loaded — handy for poking at the UI against your local companion.

## Building the submission zip

```pwsh
./build.ps1   # produces dist/asciimud-twitch-ext.zip
```

The zip contains only the files listed above, no `node_modules`, no dotfiles,
all paths relative — which is what the Twitch extension reviewer expects.

## Submission checklist

See [`docs/TWITCH_SUBMISSION.md`](../docs/TWITCH_SUBMISSION.md) for the full
step-by-step.
