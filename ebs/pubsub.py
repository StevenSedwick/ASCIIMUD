"""Twitch PubSub publisher for Extensions (Send Extension PubSub Message).

Posts to: POST https://api.twitch.tv/helix/extensions/pubsub
Auth: an EBS-signed JWT (HS256, signed with the extension secret) that lists
this extension's role + the target channel + permissions.

Limits (per Twitch docs):
  * 1 message per second per topic per channel
  * Payload <= 5 KB
  * Topics used here: "broadcast" (every viewer on the channel)

Reference: https://dev.twitch.tv/docs/extensions/reference/#send-extension-pubsub-message
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any

import httpx
import jwt  # PyJWT


_PUBSUB_URL = "https://api.twitch.tv/helix/extensions/pubsub"


class PubSubPublisher:
    def __init__(self, client_id: str, extension_secret_b64: str, owner_user_id: str) -> None:
        self.client_id = client_id
        self.secret = base64.b64decode(extension_secret_b64)
        self.owner_user_id = str(owner_user_id)
        self._http = httpx.AsyncClient(timeout=5.0)

    def _sign(self, channel_id: str) -> str:
        now = int(time.time())
        payload = {
            "exp": now + 60,
            "user_id": self.owner_user_id,
            "role": "external",
            "channel_id": channel_id,
            "pubsub_perms": {"send": ["broadcast"]},
        }
        return jwt.encode(payload, self.secret, algorithm="HS256")

    async def send_broadcast(self, channel_id: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"))
        if len(body.encode("utf-8")) > 5 * 1024:
            raise ValueError("PubSub payload exceeds 5KB cap")
        token = self._sign(channel_id)
        resp = await self._http.post(
            _PUBSUB_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Client-Id": self.client_id,
                "Content-Type": "application/json",
            },
            json={
                "target": ["broadcast"],
                "broadcaster_id": str(channel_id),
                "is_global_broadcast": False,
                "message": body,
            },
        )
        if resp.status_code >= 300:
            raise RuntimeError(f"PubSub HTTP {resp.status_code}: {resp.text[:200]}")

    async def aclose(self) -> None:
        await self._http.aclose()
