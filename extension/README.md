# ASCIIMUD Twitch Extension

The viewer-facing piece. Three views:

| View          | File                              | Audience              |
| ------------- | --------------------------------- | --------------------- |
| Viewer        | `viewer/viewer.html`              | Everyone in chat      |
| Config        | `config/config.html`              | You (broadcaster), one-time setup |
| Live config   | `live_config/live.html`           | You, while live       |

## Two data paths

1. **Free, always-on** — Twitch PubSub `broadcast` topic, ≤1 Hz, ≤5KB. The
   viewer frontend listens via `window.Twitch.ext.listen("broadcast", ...)`.
   This drives the always-visible header/meta strip.
2. **Opt-in, rich** — per-viewer WSS to your EBS at `wss://<ebs>/viewer`,
   authenticated with the helper JWT. Drives the tactical grid + feed. Viewers
   click **Enable rich view** to opt in.

## Set up in the Twitch Developer Console

1. Create a new Extension at <https://dev.twitch.tv/console/extensions/create>.
   Type: **Panel** + **Component**. Version: 0.1.0.
2. **Asset Hosting** → upload the `extension/` directory contents (or use
   "Hosted Test" with `developer rig` for local iteration).
3. **Capabilities** → enable PubSub.
4. **Settings** → copy **Client ID** and **Client Secret (Base64)** into your
   EBS `config.toml`.
5. **Allowed URLs** → add `https://<your-ebs-host>` so `fetch` and `WebSocket`
   to it aren't blocked by the extension sandbox.
6. Edit `viewer/viewer.js` and `live_config/live.js`: set `EBS_HOST` /
   broadcaster config to your real EBS hostname.

## Local dev with the Developer Rig

```bash
# Twitch Developer Rig
twitch configure
twitch extension run --version 0.1.0
```

Or just open `viewer.html` directly with `?_twitch_test=1` query stub if you
mock `window.Twitch.ext` — useful for CSS work without a live channel.

## Review

Public release requires Twitch review (1–2 weeks). Until then, the extension
runs in **Hosted Test** mode against your own channel only.
