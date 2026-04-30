"""Twitch Extension JWT verification.

Each Twitch Extension is issued a Base64-encoded shared secret. The Twitch
helper (window.Twitch.ext) hands the frontend a JWT signed with that secret
using HS256. Extension backends verify those JWTs to get a trustworthy
``channel_id``, ``opaque_user_id``, and ``role`` for every request.

Reference: https://dev.twitch.tv/docs/extensions/reference/#jwt-schema
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

import jwt  # PyJWT


@dataclass(frozen=True)
class VerifiedViewer:
    channel_id: str
    opaque_user_id: str
    user_id: str | None
    role: str  # "broadcaster" | "moderator" | "viewer" | "external"


def _decode_secret(b64: str) -> bytes:
    # Twitch dashboard provides the secret as standard Base64.
    return base64.b64decode(b64)


def verify_viewer_jwt(token: str, extension_secret_b64: str) -> VerifiedViewer:
    """Verify a Twitch helper JWT and return the trusted claims.

    Raises ``jwt.PyJWTError`` (or subclass) on any failure.
    """
    secret = _decode_secret(extension_secret_b64)
    claims = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        options={"require": ["exp", "channel_id", "user_id", "role"]},
    )
    return VerifiedViewer(
        channel_id=str(claims["channel_id"]),
        opaque_user_id=str(claims["user_id"]),  # opaque unless viewer shared id
        user_id=str(claims["user_id"]) if not str(claims["user_id"]).startswith("U") else None,
        role=str(claims["role"]),
    )
