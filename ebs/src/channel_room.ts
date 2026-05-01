import type { Env } from "./index";
import { verifyHmac } from "./hmac";
import { verifyTwitchExtJwt } from "./jwt";

interface BaseEvent {
  t: string;
  [k: string]: unknown;
}

interface SpellMeta {
  t: "spell_meta";
  id: number | string;
  [k: string]: unknown;
}

interface SpellMetaBulk {
  t: "spell_meta_bulk";
  spells: SpellMeta[];
}

interface RateBucket {
  tokens: number;
  last: number;
}

const RATE_CAPACITY = 10;
const RATE_REFILL_PER_SEC = 5;

export class ChannelRoom {
  private readonly state: DurableObjectState;
  private readonly env: Env;

  private lastSnapshot: BaseEvent | null = null;
  private readonly spellMeta: Map<string, SpellMeta> = new Map();
  private actionBarLayout: BaseEvent | null = null;
  private readonly viewers: Set<WebSocket> = new Set();
  private bucket: RateBucket = { tokens: RATE_CAPACITY, last: Date.now() };

  constructor(state: DurableObjectState, env: Env) {
    this.state = state;
    this.env = env;
    for (const ws of state.getWebSockets()) this.viewers.add(ws);
  }

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const channelId = url.searchParams.get("channelId") ?? "";

    if (request.method === "POST" && url.pathname === "/ingest") {
      return this.handleIngest(request, channelId);
    }
    if (request.method === "GET" && url.pathname === "/ws") {
      return this.handleWs(request, channelId);
    }
    return new Response("not found", { status: 404 });
  }

  private consumeToken(): boolean {
    const now = Date.now();
    const elapsed = (now - this.bucket.last) / 1000;
    this.bucket.tokens = Math.min(
      RATE_CAPACITY,
      this.bucket.tokens + elapsed * RATE_REFILL_PER_SEC,
    );
    this.bucket.last = now;
    if (this.bucket.tokens < 1) return false;
    this.bucket.tokens -= 1;
    return true;
  }

  private async handleIngest(request: Request, channelId: string): Promise<Response> {
    const auth = request.headers.get("authorization") ?? "";
    const m = /^HMAC-SHA256\s+([0-9a-fA-F]+)$/.exec(auth);
    if (!m) return new Response("unauthorized", { status: 401 });
    const providedHex = m[1]!;

    const secretHex = await this.env.SECRETS.get(`secret:${channelId}`);
    if (!secretHex) return new Response("unauthorized", { status: 401 });

    const body = await request.arrayBuffer();
    const ok = await verifyHmac(secretHex, body, providedHex);
    if (!ok) return new Response("unauthorized", { status: 401 });

    if (!this.consumeToken()) {
      return new Response("rate limited", { status: 429 });
    }

    let evt: BaseEvent;
    try {
      const text = new TextDecoder().decode(body);
      const parsed: unknown = JSON.parse(text);
      if (!parsed || typeof parsed !== "object" || typeof (parsed as { t: unknown }).t !== "string") {
        return new Response("bad event", { status: 400 });
      }
      evt = parsed as BaseEvent;
    } catch {
      return new Response("bad json", { status: 400 });
    }

    this.applyEvent(evt);
    this.broadcast(evt);
    return new Response(null, { status: 204 });
  }

  private applyEvent(evt: BaseEvent): void {
    switch (evt.t) {
      case "snapshot":
        this.lastSnapshot = evt;
        break;
      case "spell_meta": {
        const sm = evt as SpellMeta;
        if (sm.id !== undefined && sm.id !== null) {
          this.spellMeta.set(String(sm.id), sm);
        }
        break;
      }
      case "spell_meta_bulk": {
        const bulk = evt as unknown as SpellMetaBulk;
        if (Array.isArray(bulk.spells)) {
          for (const s of bulk.spells) {
            if (s && s.id !== undefined && s.id !== null) {
              this.spellMeta.set(String(s.id), s);
            }
          }
        }
        break;
      }
      case "action_bar":
        this.actionBarLayout = evt;
        break;
      default:
        break;
    }
  }

  private broadcast(evt: BaseEvent): void {
    const payload = JSON.stringify(evt);
    const dead: WebSocket[] = [];
    for (const ws of this.viewers) {
      try {
        ws.send(payload);
      } catch {
        dead.push(ws);
      }
    }
    for (const ws of dead) {
      this.viewers.delete(ws);
      try {
        ws.close(1011, "send failed");
      } catch {
        // ignore
      }
    }
  }

  private async handleWs(request: Request, channelId: string): Promise<Response> {
    if (request.headers.get("upgrade") !== "websocket") {
      return new Response("expected websocket", { status: 426 });
    }
    const url = new URL(request.url);
    const token = url.searchParams.get("jwt");
    if (!token) return new Response("unauthorized", { status: 401 });

    const pem = this.env.TWITCH_EXT_SECRETS;
    if (!pem) return new Response("server misconfigured", { status: 500 });
    const secrets = pem.split(",").map(s => s.trim()).filter(Boolean);

    let claims;
    try {
      claims = await verifyTwitchExtJwt(token, secrets);
    } catch {
      return new Response("unauthorized", { status: 401 });
    }
    if (claims.channel_id !== channelId) {
      return new Response("forbidden", { status: 403 });
    }

    const pair = new WebSocketPair();
    const client = pair[0];
    const server = pair[1];

    this.state.acceptWebSocket(server);
    this.viewers.add(server);

    this.sendReplay(server);

    return new Response(null, { status: 101, webSocket: client });
  }

  private sendReplay(ws: WebSocket): void {
    try {
      if (this.lastSnapshot) ws.send(JSON.stringify(this.lastSnapshot));
      if (this.spellMeta.size > 0) {
        const bulk: SpellMetaBulk = {
          t: "spell_meta_bulk",
          spells: Array.from(this.spellMeta.values()),
        };
        ws.send(JSON.stringify(bulk));
      }
      if (this.actionBarLayout) ws.send(JSON.stringify(this.actionBarLayout));
    } catch {
      // viewer will be pruned on next broadcast
    }
  }

  async webSocketMessage(_ws: WebSocket, _message: string | ArrayBuffer): Promise<void> {
    // Read-only feed; ignore client messages.
  }

  async webSocketClose(ws: WebSocket, code: number, _reason: string, _wasClean: boolean): Promise<void> {
    this.viewers.delete(ws);
    try {
      ws.close(code, "bye");
    } catch {
      // ignore
    }
  }

  async webSocketError(ws: WebSocket, _error: unknown): Promise<void> {
    this.viewers.delete(ws);
  }
}
