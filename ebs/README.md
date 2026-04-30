# ASCIIMUD EBS

The Extension Backend Service. One container, two jobs:

1. **Ingest** the companion's event stream from your home PC over an
   authenticated outbound WebSocket (`/ingest`).
2. **Fan out** to viewers two ways:
   - **PubSub broadcast** — 1 Hz, ≤5KB digest, reaches every viewer of the
     channel for free.
   - **Per-viewer WSS** — full-fidelity stream for opted-in viewers
     (`/viewer`), authenticated with the Twitch helper JWT.

## Local dev

```powershell
cd ebs
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy config.example.toml config.toml
# fill in: ingest.shared_secret, twitch.client_id,
#          twitch.extension_secret, twitch.owner_user_id
uvicorn server:app --host 0.0.0.0 --port 8080
```

Health check: `GET /healthz`.

## Deploy

```bash
docker build -t asciimud-ebs .
docker run -p 8080:8080 -v $(pwd)/config.toml:/app/config.toml asciimud-ebs
```

Tested deploy targets: Fly.io, Render, Railway. Any container host with WSS
ingress and a stable hostname works.

## Twitch dashboard wiring

In the Extension dashboard → **Asset Hosting** and **Capabilities**:

- **Allowed URLs** must include your EBS hostname.
- **Required broadcaster configuration** = on (so config.html runs first).
- **EBS URL** is informational; the frontend connects directly via WSS.

## Security notes

- `ingest.shared_secret` protects `/ingest`. Treat it like a database password.
- Never expose `extension_secret` to the browser; only the EBS uses it.
- The viewer JWT carries `opaque_user_id` only by default; viewers must opt in
  to share their real `user_id`.
