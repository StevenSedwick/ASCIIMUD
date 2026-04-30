// ASCIIMUD overlay — connects to companion WS, renders state for chat.
const WS_URL = (new URLSearchParams(location.search)).get("ws")
            || "ws://127.0.0.1:8765/ws";

const $ = (id) => document.getElementById(id);
const els = {
  zone: $("zone"), player: $("player"), hp: $("hp"), mp: $("mp"),
  severity: $("severity"), grid: $("grid"), feed: $("feed"), status: $("status"),
};

const COLS = 60, ROWS = 20;

function blankGrid() {
  return Array.from({ length: ROWS }, () => ".".repeat(COLS));
}

function renderGrid(snap) {
  const g = blankGrid().map(r => r.split(""));
  const pr = Math.floor(ROWS / 2), pc = Math.floor(COLS / 2);
  g[pr][pc] = "@";
  if (snap.target) g[pr][pc + 4] = snap.target.hostile ? "X" : "N";
  els.grid.textContent = g.map(r => r.join("")).join("\n");
}

function renderHeader(snap) {
  const z = snap.zone || {};
  const p = snap.player || {};
  els.zone.textContent = z.subzone && z.subzone !== z.name
    ? `${z.name} : ${z.subzone}` : (z.name || "—");
  els.player.textContent = `Lv${p.level ?? "?"} ${p.name ?? "?"}`;
  els.hp.textContent = `HP ${p.hp ?? "?"}/${p.hpMax ?? "?"}`;
  els.mp.textContent = `MP ${p.mp ?? "?"}/${p.mpMax ?? "?"}`;
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
    default:
      break;
  }
}

function connect() {
  els.status.textContent = `connecting ${WS_URL}…`;
  const ws = new WebSocket(WS_URL);
  ws.onopen    = () => { els.status.textContent = "connected"; };
  ws.onclose   = () => { els.status.textContent = "disconnected — retrying"; setTimeout(connect, 2000); };
  ws.onerror   = () => { try { ws.close(); } catch (_) {} };
  ws.onmessage = (m) => { try { handle(JSON.parse(m.data)); } catch (e) { console.error(e); } };
}

renderGrid({});
connect();
