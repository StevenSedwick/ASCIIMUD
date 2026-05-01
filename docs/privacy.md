# ASCIIMUD — Privacy Policy

_Last updated: 2026-04-30_

ASCIIMUD is a Twitch video-overlay extension that displays real-time game-state
information published by the broadcaster.

## What we collect

- **From viewers:** nothing. The extension does **not** request the viewer's
  identity, email address, or any other personal information from Twitch.
- **From broadcasters:** the URL of the broadcaster's own EBS endpoint
  (a Cloudflare Worker URL), saved to Twitch's Configuration Service.
- **From the broadcaster's PC:** game-state snapshots produced by the
  broadcaster's own companion app — character name, level, location
  coordinates, hit points, mana, target information, recent combat events.
  This data is published *by the broadcaster, to their own viewers*; it is
  the same information visible on stream.

## What we transmit

When you load a channel running the ASCIIMUD extension, your browser opens
a WebSocket connection to the broadcaster's EBS endpoint to receive game-state
updates. The connection carries a short-lived **opaque JWT** issued by Twitch
which identifies the channel only — never the viewer.

## What we store

- **In your browser:** a single `localStorage` key (`asciimud:expanded`) that
  remembers whether you collapsed or expanded the overlay. This is local to
  your browser and is never transmitted.
- **On the broadcaster's EBS:** the most recent game-state snapshot, kept in
  memory only, replaced as new snapshots arrive.

## What we do **not** do

- We do **not** use cookies.
- We do **not** track you across sessions or channels.
- We do **not** sell or share data with third parties.
- We do **not** ingest data from anyone other than the broadcaster's own
  companion app, which is HMAC-authenticated.

## Contact

For privacy questions, email the broadcaster who installed the extension on
their channel, or open an issue at
<https://github.com/StevenSedwick/ASCIIMUD>.
