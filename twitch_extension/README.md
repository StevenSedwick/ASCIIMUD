# ASCIIMUD Twitch Extension

A small video-overlay component that shows the streamer's HP/MP, current zone,
and target HP in real time, fed by the ASCIIMUD addon → companion → EBS pipeline.

## Layout

```
twitch_extension/
├── frontend/                 ← uploaded as the "Video - Component" asset
│   ├── viewer.html
│   ├── viewer.js
│   └── viewer.css
└── config/                   ← uploaded as the "Config" asset
    └── config.html
```

## Configure on the Twitch Developer Console

1. Create a new extension at https://dev.twitch.tv/console/extensions
2. **Type**: Video — Component (preferred) or Overlay
3. **Asset Hosting**: upload contents of `frontend/` as the viewer asset and
   `config.html` as the config asset.
4. **Required URLs**:
   - Viewer Path: `viewer.html`
   - Config Path: `config.html`
   - Live Config Path: `config.html` (same)
5. **Backend Service URLs**: set to your deployed EBS, e.g.
   `https://asciimud-ebs.fly.dev`
6. **Extension Capabilities**:
   - Send PubSub Messages: ✅
   - Receive PubSub Messages: ✅
   - Make External HTTP Requests: ✅ (whitelist your EBS hostname)
7. **Allowlisted Config URLs**: your EBS hostname (so config.html can call it
   if you add that flow later).

## Submission checklist

- [ ] Privacy policy URL (required by Twitch even for client-side overlays)
- [ ] Terms of service URL
- [ ] Support email
- [ ] At least 3 screenshots (1280×720 or higher) of the overlay rendering
- [ ] A 30s+ demo video of the extension working live on a stream
- [ ] Description (`<350 chars`) and detailed description
- [ ] Test extension on at least one channel before submitting for review

## How data flows

```
Streamer's WoW
   └─ ASCIIMUD addon takes a screenshot every 2s with state-encoded grid
       └─ companion.py (local) decodes + forwards as snapshot event
           └─ EBS.fly.dev (cloud) receives via WSS /ingest
               ├─ Twitch PubSub broadcast (1 Hz digest, all viewers)
               └─ Per-viewer WSS rich stream (5 Hz, opted-in via Helper JWT)
                   └─ This extension viewer.html renders bars + zone
```

See `../ebs/README.md` for cloud setup.
