# ASCIIMUD — Terms of Service

_Last updated: 2026-04-30_

These terms govern your use of the ASCIIMUD Twitch extension ("the
extension") and the supporting Cloudflare Worker EBS ("the EBS"). The
extension is provided free of charge, as-is, by the broadcaster who installed
it on their channel.

## Acceptable use

By using the extension, you agree to:

- Use it solely for its intended purpose — viewing the broadcaster's
  in-game state on top of their stream.
- Not attempt to circumvent the JWT authentication on the EBS WebSocket
  endpoint, or attempt to inject events into another channel's data feed.
- Not attempt to overload the EBS with abnormal connection or message rates.

## No warranty

The extension and EBS are provided **"AS IS"** and **WITHOUT WARRANTY OF
ANY KIND**, express or implied, including but not limited to merchantability,
fitness for a particular purpose, and non-infringement. The broadcaster and
the project authors are **not liable** for any damages arising from use of
the extension.

## Service availability

The EBS runs on Cloudflare Workers and is subject to Cloudflare's uptime.
Snapshots may be delayed or dropped; the extension is a non-essential overlay
on top of the live video stream.

## Changes

These terms may change without notice. The current version is always
available at <https://github.com/StevenSedwick/ASCIIMUD/blob/main/docs/terms.md>.

## Open source

The extension is open source under the same license as the parent ASCIIMUD
repository. See `LICENSE` in the repository root.
