# ASCIIMUD EBS — Cloudflare Workers

Extension Backend Service for the ASCIIMUD Twitch extension. The local
companion (`companion/companion.py`) HMAC-signs and POSTs game-state events
to this Worker; a per-channel Durable Object (`ChannelRoom`) fans them out
over WebSockets to viewers running the Twitch extension.

## Live deployment

- **Worker URL:** <https://asciimud-ebs.goreakis2.workers.dev>
- **Health check:** <https://asciimud-ebs.goreakis2.workers.dev/healthz> → `{"ok": true}`
- **KV namespace (`SECRETS`) id:** `6d8b18982e0a4ad4b1cc696d4fc0b52e` (already in `wrangler.toml`)

## Endpoints

| Method | Path                  | Auth                             | Notes                                       |
| ------ | --------------------- | -------------------------------- | ------------------------------------------- |
| GET    | `/healthz`            | —                                | `{"ok": true}`                              |
| POST   | `/ingest/:channelId`  | `Authorization: HMAC-SHA256 <hex>` over raw body | Companion → EBS event upload. 5 ev/s, burst 10. |
| GET    | `/ws/:channelId`      | `?jwt=<twitch-ext-jwt>` (HS256)  | Viewer feed. JWT `channel_id` must match.   |

On WS connect the room replays `lastSnapshot`, then a `spell_meta_bulk`
of all known spells, then the latest `action_bar` layout, before streaming
live events.

## Quickstart

```bash
cd ebs
npm install

# 1) KV namespace for per-channel HMAC secrets.
#    (Already done for this deployment — id 6d8b18982e0a4ad4b1cc696d4fc0b52e.)
npx wrangler kv namespace create SECRETS
# Copy the printed `id` into wrangler.toml under [[kv_namespaces]].

# 2) Provision a per-channel HMAC secret (hex string shared with companion).
npx wrangler kv key put --namespace-id <id> "secret:<channelId>" "<hexsecret>" --remote

# 3) Twitch extension shared secret(s) (HS256, base64-encoded; from the
#    Twitch Developer Console -> Extension Settings -> Client Configuration).
#    Pass a comma-separated list to support secret rotation. Stored as a
#    Worker secret (overrides the empty [vars] default).
npx wrangler secret put TWITCH_EXT_SECRETS

# 4) Local dev (no Twitch creds needed for /healthz and /ingest mock).
npm run dev   # http://127.0.0.1:8787

# 5) Deploy.
npm run deploy
```

## Type checking

```bash
npm run typecheck
```

## Auth details

### Ingest HMAC

```
sig = hex(HMAC_SHA256(secret_bytes, raw_request_body))
Authorization: HMAC-SHA256 <sig>
```

The secret stored in KV at `secret:<channelId>` must be a hex string; the
companion uses the same hex bytes. Mismatched / missing → `401`.

### Viewer JWT

The Twitch extension SDK provides a signed JWT via `Twitch.ext.onAuthorized`.
The Worker verifies it with HS256 against `TWITCH_EXT_SECRETS` (one or more
base64-encoded shared secrets from the Twitch developer console). Multiple
secrets allow rotation: the JWT validates if **any** active secret signs it.
The `channel_id` claim must match the URL segment.

## Layout

```
ebs/
  wrangler.toml
  package.json
  tsconfig.json
  src/
    index.ts          # router; forwards to ChannelRoom DO
    channel_room.ts   # Durable Object: state + ingest + WS fanout
    hmac.ts           # SubtleCrypto HMAC-SHA256 verify
    jwt.ts            # jose HS256 verify (Twitch ext JWT)
```

This is Phase 3A only — the companion-side push client and the Twitch
extension viewer panel arrive in 3B/3C.
