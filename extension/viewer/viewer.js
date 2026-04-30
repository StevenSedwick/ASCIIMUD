// ASCIIMUD viewer extension frontend.
//
// Two data paths:
//   1. Always-on: PubSub broadcasts (1 Hz digest) via Twitch.ext.listen("broadcast", ...)
//   2. Opt-in: per-viewer WSS to the EBS for the rich stream.

const EBS_HOST = "ebs.example.com"; // <-- replace with your deployed EBS hostname

const $ = (id) => document.getElementById(id);
const els = {
  zone: $("zone"), sev: $("sev"), player: $("player"), hp: $("hp"),
  target: $("target"), rich: $("rich"), grid: $("grid"), feed: $("feed"),
  optIn: $("opt-in"), status: $("status"),
};

let viewerJwt = null;
let channelId = null;
let ws = null;
let richEnabled = false;

function setStatus(s) { els.status.textContent = s; }

function applyDigest(d) {
  els.zone.textContent = d.z || "—";
  els.player.textContent = d.lvl ? `Lv${d.lvl}` : "—";
  els.hp.textContent = `HP ${d.hpPct ?? "—"}%`;
  els.target.textContent = d.tgt
    ? `${d.tgtHostile ? "⚔ " : "· "}${d.tgt}`
    : "no target";
  els.sev.dataset.level = String(d.sev ?? 0);
  els.sev.textContent = `SEV ${d.sev ?? 0}`;
}

function applyRich(evt) {
  if (evt.t === "snapshot") {
    const s = evt.data;
    // reuse digest renderer for the cheap fields
    applyDigest({
      v: 1, sev: 0, z: s.zone?.subzone || s.zone?.name,
      lvl: s.player?.level,
      hpPct: s.player?.hpMax ? Math.round(100 * s.player.hp / s.player.hpMax) : 0,
      tgt: s.target?.name, tgtHostile: !!s.target?.hostile,
    });
    // Tactical grid (placeholder render)
    const COLS = 60, ROWS = 12;
    const grid = Array.from({ length: ROWS }, () => ".".repeat(COLS).split(""));
    const pr = (ROWS / 2) | 0, pc = (COLS / 2) | 0;
    grid[pr][pc] = "@";
    if (s.target) grid[pr][pc + 4] = s.target.hostile ? "X" : "N";
    els.grid.textContent = grid.map(r => r.join("")).join("\n");
  } else if (evt.t === "severity") {
    els.sev.dataset.level = String(evt.level);
    els.sev.textContent = `SEV ${evt.level}`;
  } else if (evt.t === "death") {
    pushFeed(`*** ${evt.player} has died ***`, true);
  }
}

function pushFeed(line, danger) {
  const div = document.createElement("div");
  div.className = "line" + (danger ? " danger" : "");
  div.textContent = line;
  els.feed.appendChild(div);
  while (els.feed.childElementCount > 24) els.feed.firstElementChild.remove();
}

function connectRich() {
  if (!viewerJwt) return;
  const url = `wss://${EBS_HOST}/viewer?token=${encodeURIComponent(viewerJwt)}`;
  ws = new WebSocket(url);
  ws.onopen    = () => setStatus("rich: connected");
  ws.onclose   = () => { setStatus("rich: disconnected — retrying"); setTimeout(connectRich, 2000); };
  ws.onerror   = () => { try { ws.close(); } catch (_) {} };
  ws.onmessage = (m) => { try { applyRich(JSON.parse(m.data)); } catch (e) { console.error(e); } };
}

window.Twitch.ext.onAuthorized((auth) => {
  viewerJwt = auth.token;
  channelId = auth.channelId;
  setStatus("digest: connected");
});

window.Twitch.ext.listen("broadcast", (_target, _ctype, raw) => {
  try { applyDigest(JSON.parse(raw)); } catch (e) { console.error(e); }
});

els.optIn.addEventListener("click", () => {
  if (richEnabled) return;
  richEnabled = true;
  els.optIn.disabled = true;
  els.optIn.textContent = "Rich view enabled";
  els.rich.hidden = false;
  connectRich();
});
