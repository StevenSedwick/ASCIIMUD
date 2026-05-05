import type { Env } from "./index";
import { verifyHmac } from "./hmac";
import { verifyTwitchExtJwt } from "./jwt";
import { INTERFACE_HTML } from "./public_pages/interface";

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
    if (request.method === "GET" && url.pathname === "/state") {
      return this.handleState();
    }
    if (request.method === "GET" && url.pathname === "/map") {
      return this.handleMap(channelId);
    }
    if (request.method === "GET" && url.pathname === "/interface") {
      return this.handleInterface(channelId);
    }
    if (request.method === "GET" && url.pathname === "/spells") {
      return this.handleSpells();
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

  private handleState(): Response {
    if (!this.lastSnapshot) {
      return new Response(null, { status: 204 });
    }
    return new Response(JSON.stringify(this.lastSnapshot), {
      headers: {
        "content-type": "application/json",
        "access-control-allow-origin": "*",
        "cache-control": "no-store",
      },
    });
  }

  private handleMap(channelId: string): Response {
    const html = MAP_HTML.replace("__CHANNEL_ID__", channelId);
    return new Response(html, {
      headers: { "content-type": "text/html;charset=utf-8" },
    });
  }

  private handleInterface(channelId: string): Response {
    const html = INTERFACE_HTML
      .replace("__CHANNEL_ID__", channelId)
      .replace("__ZONE_DATA__", zoneDataToJs());
    return new Response(html, {
      headers: { "content-type": "text/html;charset=utf-8" },
    });
  }

  private handleSpells(): Response {
    return new Response(
      JSON.stringify({ spells: Array.from(this.spellMeta.values()) }),
      {
        headers: {
          "content-type": "application/json",
          "access-control-allow-origin": "*",
          "cache-control": "no-store",
        },
      },
    );
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

// ---------------------------------------------------------------------------
// Zone table: ASCIIMUD u16 polynomial hash → Wowhead zone ID + display name.
// Zone images served from: https://wow.zamimg.com/images/wow/maps/enus/zoom/{zoneId}.jpg
// ---------------------------------------------------------------------------
const ZONE_DATA: Record<number, { name: string; zoneId: number }> = {
  0x5043: { name: "Dun Morogh",           zoneId: 1    },
  0x4F23: { name: "Badlands",             zoneId: 3    },
  0xF2DF: { name: "Blasted Lands",        zoneId: 4    },
  0x2E66: { name: "Swamp of Sorrows",     zoneId: 8    },
  0x3ED4: { name: "Elwynn Forest",        zoneId: 12   },
  0x6A37: { name: "Durotar",             zoneId: 14   },
  0x2377: { name: "Dustwallow Marsh",     zoneId: 15   },
  0x9722: { name: "Azshara",             zoneId: 16   },
  0x30DC: { name: "The Barrens",          zoneId: 17   },
  0x4AEF: { name: "Stranglethorn Vale",   zoneId: 33   },
  0xD3DE: { name: "Alterac Mountains",    zoneId: 36   },
  0x41B7: { name: "Loch Modan",          zoneId: 38   },
  0xC145: { name: "Deadwind Pass",        zoneId: 41   },
  0xC7A0: { name: "Redridge Mountains",   zoneId: 44   },
  0xC54B: { name: "Arathi Highlands",     zoneId: 45   },
  0xEF25: { name: "Burning Steppes",      zoneId: 46   },
  0x36D4: { name: "The Hinterlands",      zoneId: 47   },
  0x3985: { name: "The Hinterlands",      zoneId: 47   },
  0xE247: { name: "Searing Gorge",        zoneId: 51   },
  0xA82C: { name: "Tirisfal Glades",      zoneId: 85   },
  0x23A0: { name: "Silverpine Forest",    zoneId: 130  },
  0x5F3B: { name: "Teldrassil",          zoneId: 141  },
  0xEE97: { name: "Darkshore",           zoneId: 148  },
  0x3EBF: { name: "Mulgore",             zoneId: 215  },
  0x81C9: { name: "Hillsbrad Foothills",  zoneId: 267  },
  0xC7E8: { name: "Western Plaguelands",  zoneId: 28   },
  0x5FDA: { name: "Eastern Plaguelands",  zoneId: 139  },
  0x1763: { name: "Ashenvale",           zoneId: 331  },
  0xDB90: { name: "Feralas",             zoneId: 357  },
  0x5B9A: { name: "Felwood",             zoneId: 361  },
  0x5CD4: { name: "Desolace",            zoneId: 405  },
  0x406C: { name: "Stonetalon Mountains", zoneId: 406  },
  0xD682: { name: "Thousand Needles",     zoneId: 400  },
  0x701C: { name: "Tanaris",             zoneId: 440  },
  0xDB1C: { name: "Un'Goro Crater",       zoneId: 490  },
  0xA31C: { name: "Moonglade",           zoneId: 493  },
  0x8532: { name: "Winterspring",        zoneId: 618  },
  0x7462: { name: "Wetlands",            zoneId: 11   },
  0x6DCA: { name: "Westfall",            zoneId: 40   },
  0x3105: { name: "Silithus",            zoneId: 1377 },
  0xE0E6: { name: "Darnassus",           zoneId: 1657 },
  0xF37F: { name: "Ironforge",           zoneId: 1537 },
  0x604C: { name: "Orgrimmar",           zoneId: 1637 },
  0xDBFA: { name: "Stormwind City",       zoneId: 1519 },
  0x10EF: { name: "Thunder Bluff",        zoneId: 1638 },
  0xD023: { name: "Undercity",           zoneId: 1497 },
};

// Serialise to JS object literal for inlining into the map page.
function zoneDataToJs(): string {
  return (
    "{\n" +
    Object.entries(ZONE_DATA)
      .map(([k, v]) => `  ${k}:{name:${JSON.stringify(v.name)},zoneId:${v.zoneId}}`)
      .join(",\n") +
    "\n}"
  );
}

// ---------------------------------------------------------------------------
// Inline HTML for the /map page.
// ---------------------------------------------------------------------------
const MAP_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ASCIIMUD — Live Map</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0c0b09;color:#d4c9a8;font-family:monospace;display:flex;
     flex-direction:column;align-items:center;padding:1rem;min-height:100vh}
h1{font-size:.85rem;letter-spacing:.25em;color:#6b5d40;margin:.75rem 0 .25rem}
#zone{font-size:1.3rem;color:#d4a955;min-height:1.6rem;margin:.35rem 0}
#hud{font-size:.78rem;color:#a08060;min-height:1.1rem;margin-bottom:.5rem}
#wrap{position:relative;display:inline-block;line-height:0;
      border:1px solid #2a2520;box-shadow:0 0 20px #000}
#img{display:block;max-width:520px;width:90vw;min-height:60px;
     background:#111;object-fit:contain}
#dot{position:absolute;width:14px;height:14px;border-radius:50%;
     background:#e83838;border:2px solid #fff8;
     transform:translate(-50%,-50%);pointer-events:none;
     transition:left .8s ease,top .8s ease}
#dot.combat{background:#ff2222;box-shadow:0 0 8px #ff2222aa}
#dot.dead{background:#555;border-color:#888}
#status{font-size:.7rem;color:#4a4035;margin-top:.5rem;min-height:.9rem}
footer{font-size:.65rem;color:#3a3028;margin-top:1.5rem;text-align:center;line-height:1.8}
footer a{color:#5a4e38;text-decoration:none}
footer a:hover{color:#d4a955}
</style>
</head>
<body>
<h1>[ ASCIIMUD LIVE MAP ]</h1>
<div id="zone">Waiting for data&hellip;</div>
<div id="hud"></div>
<div id="wrap">
  <img id="img" src="" alt="zone map" onerror="this.style.display='none'">
  <div id="dot"></div>
</div>
<div id="status">Connecting&hellip;</div>
<footer>
  Map tiles &copy; <a href="https://www.wowhead.com" target="_blank" rel="noopener">Wowhead</a>
  &nbsp;&bull;&nbsp;
  <a href="https://www.curseforge.com/wow/addons/textadventure" target="_blank" rel="noopener">Get the ASCIIMUD addon</a>
</footer>
<script>
const CHANNEL_ID="__CHANNEL_ID__";
const ZONES=${zoneDataToJs()};
let lastHash=null,lastZoneId=null;

function cls(hpPct,combat,hp){
  if(hp===0)return"dead";
  if(combat)return"combat";
  return"";
}

function update(snap){
  if(!snap||snap.t!=="snapshot")return;
  const d=snap.data||{};
  const p=d.player||{};
  const z=d.zone||{};
  const hash=z.hash;
  const mapX=z.mapX??128;
  const mapY=z.mapY??128;
  const combat=!!d.combat;
  const hp=p.hpPct??100;
  const lvl=p.level??"?";
  const cls_=p.class??"?";
  const race=p.race??"";

  const zi=ZONES[hash]||{};
  const zoneName=zi.name||(hash?"Unknown (0x"+hash.toString(16).toUpperCase()+")":"Unknown zone");

  document.getElementById("zone").textContent=zoneName;
  document.getElementById("hud").textContent=
    (race?race+" ":"")+"Level "+lvl+" "+cls_
    +"  |  HP "+hp+"%"
    +(combat?"  |  ⚔ IN COMBAT":"");

  const zoneId=zi.zoneId;
  if(hash!==lastHash){
    lastHash=hash;
    const img=document.getElementById("img");
    if(zoneId&&zoneId!==lastZoneId){
      lastZoneId=zoneId;
      img.style.display="";
      img.src="https://wow.zamimg.com/images/wow/maps/enus/zoom/"+zoneId+".jpg";
    }
  }

  const dot=document.getElementById("dot");
  dot.style.left=(mapX/255*100).toFixed(2)+"%";
  dot.style.top=(mapY/255*100).toFixed(2)+"%";
  dot.className=cls(hp,combat,p.hp);
  document.getElementById("status").textContent=
    "Last update: "+new Date().toLocaleTimeString();
}

async function poll(){
  try{
    const r=await fetch("/state/"+CHANNEL_ID);
    if(r.status===200)update(await r.json());
    else if(r.status===204)document.getElementById("status").textContent="No data yet — is the game running?";
    else document.getElementById("status").textContent="Server returned "+r.status;
  }catch(e){
    document.getElementById("status").textContent="Connection error — retrying\u2026";
  }
}

poll();
setInterval(poll,2000);
</script>
</body>
</html>`;

