import { jwtVerify, type JWTPayload } from "jose";

export interface TwitchExtClaims {
  channel_id: string;
  role: string;
  user_id?: string;
}

// Cache decoded secret bytes per base64 string to avoid re-decoding on every request.
const keyCache = new Map<string, Uint8Array>();

function decodeBase64(b64: string): Uint8Array {
  const binary = atob(b64);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
  return out;
}

function getKeyBytes(secretB64: string): Uint8Array {
  let bytes = keyCache.get(secretB64);
  if (!bytes) {
    bytes = decodeBase64(secretB64);
    keyCache.set(secretB64, bytes);
  }
  return bytes;
}

/**
 * Verify a Twitch Extension JWT.
 *
 * Twitch ext JWTs are signed HS256 using the extension's shared secret
 * (a base64-encoded string from the Twitch developer console). The frontend
 * receives the JWT via Twitch.ext.onAuthorized() and forwards it to the EBS.
 *
 * Multiple secrets can be active simultaneously during rotation — pass each
 * candidate in `secretsB64` and we accept the JWT if any of them validates.
 */
export async function verifyTwitchExtJwt(
  token: string,
  secretsB64: string[],
): Promise<TwitchExtClaims> {
  let lastErr: unknown = new Error("no secrets configured");
  for (const secret of secretsB64) {
    if (!secret) continue;
    try {
      const { payload } = await jwtVerify(token, getKeyBytes(secret), {
        algorithms: ["HS256"],
      });
      return extractClaims(payload);
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr;
}

function extractClaims(payload: JWTPayload): TwitchExtClaims {
  const p = payload as JWTPayload & {
    channel_id?: unknown;
    role?: unknown;
    user_id?: unknown;
  };
  if (typeof p.channel_id !== "string" || typeof p.role !== "string") {
    throw new Error("missing channel_id or role claim");
  }
  const claims: TwitchExtClaims = { channel_id: p.channel_id, role: p.role };
  if (typeof p.user_id === "string") claims.user_id = p.user_id;
  return claims;
}
