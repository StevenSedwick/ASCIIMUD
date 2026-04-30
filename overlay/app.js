// ASCIIMUD overlay — connects to companion WS, renders state for chat.
const WS_URL = (new URLSearchParams(location.search)).get("ws")
            || "ws://127.0.0.1:8765/ws";

const $ = (id) => document.getElementById(id);
const els = {
  zone: $("zone"),
  hpFill: $("hpFill"), hpPct: $("hpPct"),
  mpFill: $("mpFill"), mpPct: $("mpPct"),
  targetCard: $("targetCard"), targetLabel: $("targetLabel"),
  targetFill: $("targetFill"), targetPct: $("targetPct"), targetMeta: $("targetMeta"),
  severity: $("severity"),
  grid: $("grid"),
  feed: $("feed"),
  status: $("status"),
};

const COLS = 60, ROWS = 18;

// Zone-hash → human name lookup. Fnv1a8(name) computed by the addon.
// Add zones as you discover them (companion logs the hash).
const ZONE_NAMES = {
  // Pre-fill examples; companion can also resolve via combat-log SOURCE_GUID context.
  // 0xF014: "Tirisfal Glades",
};

function blankGrid() {
  return Array.from({ length: ROWS }, () => ".".repeat(COLS));
}

function renderGrid(snap) {
  const g = blankGrid().map(r => r.split(""));
  const pr = Math.floor(ROWS / 2), pc = Math.floor(COLS / 2);
  g[pr][pc] = "@";
  if (snap.target && snap.target.exists) {
    g[pr][pc + 4] = snap.target.hostile ? "X" : "N";
  }
  els.grid.textContent = g.map(r => r.join("")).join("\n");
}

function setBarTier(fillEl, pct) {
  if (pct >= 60)      fillEl.dataset.tier = "good";
  else if (pct >= 30) fillEl.dataset.tier = "mid";
  else                fillEl.dataset.tier = "low";
}

function renderHeader(snap) {
  const z = snap.zone || {};
  const p = snap.player || {};
  const t = snap.target;

  // Zone label (name lookup falls back to hex hash).
  const zoneLabel = z.name
    || ZONE_NAMES[z.hash]
    || (z.hash != null ? `zone#${z.hash.toString(16).toUpperCase().padStart(4, "0")}` : "—");
  els.zone.textContent = zoneLabel.toUpperCase();

  // Player vitals.
  if (p.hpPct != null) {
    els.hpFill.style.width = p.hpPct + "%";
    setBarTier(els.hpFill, p.hpPct);
    els.hpPct.textContent = p.hpPct + " %";
  }
  if (p.mpPct != null) {
    els.mpFill.style.width = p.mpPct + "%";
    els.mpPct.textContent = p.mpPct + " %";
  }

  // Target.
  if (t && t.exists) {
    document.body.dataset.target = "1";
    els.targetLabel.textContent = t.hostile ? "HOSTILE TARGET" : "FRIENDLY TARGET";
    els.targetPct.textContent = (t.hpPct ?? 0) + " %";
    els.targetFill.style.width = (t.hpPct ?? 0) + "%";
    els.targetFill.dataset.faction = t.hostile ? "hostile" : "friendly";
    els.targetMeta.textContent = t.hostile ? "ENGAGED" : "ALLY";
  } else {
    document.body.dataset.target = "0";
    els.targetLabel.textContent = "NO TARGET";
    els.targetPct.textContent = "— %";
    els.targetFill.style.width = "0%";
    els.targetMeta.textContent = "—";
  }

  document.body.dataset.combat = snap.combat ? "1" : "0";

  // Auto-derive severity if not pushed explicitly.
  setSeverity(deriveSeverity(snap));
}

function deriveSeverity(snap) {
  const hp = snap.player?.hpPct ?? 100;
  const inCombat = !!snap.combat;
  if (hp <= 15) return 5;
  if (hp <= 30 && inCombat) return 4;
  if (inCombat && snap.target?.hostile) return 3;
  if (inCombat) return 2;
  if (hp < 70)  return 1;
  return 0;
}

function pushFeed(line, klass) {
  const div = document.createElement("div");
  div.className = "line" + (klass ? " " + klass : "");
  div.textContent = line;
  els.feed.appendChild(div);
  while (els.feed.childElementCount > 60) els.feed.firstElementChild.remove();
  els.feed.scrollTop = els.feed.scrollHeight;
}

function setSeverity(level) {
  els.severity.dataset.level = String(level);
  els.severity.textContent = `SEV ${level}`;
  document.body.dataset.severity = String(level);
}

function setStatus(text, live) {
  els.status.textContent = text;
  els.status.classList.toggle("live", !!live);
}

function handle(evt) {
  switch (evt.t) {
    case "snapshot":
      renderHeader(evt.data);
      renderGrid(evt.data);
      break;
    case "severity":
      setSeverity(evt.level);
      break;
    case "death":
      pushFeed(`*** ${evt.player} has died ***`, "death");
      break;
    case "combat": {
      if (evt.event === "UNIT_DIED") {
        pushFeed(`☠ ${evt.dst || "?"} dies.`, "death");
      }
      break;
    }
    case "combat_summary": {
      const arrow = evt.direction === "out" ? "→" : evt.direction === "in" ? "←" : "·";
      const who = evt.direction === "out" ? evt.dst : evt.src;
      const cls = evt.direction === "in" ? "in" : "out";
      const hits = evt.count > 1 ? ` x${evt.count}` : "";
      const total = evt.total ? ` (${evt.total})` : "";
      pushFeed(`${arrow} ${evt.spell || evt.event}${hits}${total} ${who || ""}`.trim(), cls);
      break;
    }
    default:
      break;
  }
}

function connect() {
  setStatus(`connecting ${WS_URL}…`, false);
  const ws = new WebSocket(WS_URL);
  ws.onopen    = () => { setStatus("LIVE", true); };
  ws.onclose   = () => { setStatus("disconnected — retrying", false); setTimeout(connect, 2000); };
  ws.onerror   = () => { try { ws.close(); } catch (_) {} };
  ws.onmessage = (m) => { try { handle(JSON.parse(m.data)); } catch (e) { console.error(e); } };
}

renderGrid({});
renderHeader({ player: {}, zone: {} });
connect();
