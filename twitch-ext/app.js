// ASCIIMUD overlay — Phase-1 theatrical UI
// In OBS browser-source mode, WS URL is read from ?ws= or defaults to localhost.
// In Twitch-extension mode, viewer.js sets window.ASCIIMUD_WS_URL and calls
// window.ASCIIMUD_connect() after Twitch.ext.onAuthorized fires.
function _resolveWsUrl() {
  if (typeof window !== "undefined" && window.ASCIIMUD_WS_URL) return window.ASCIIMUD_WS_URL;
  return (new URLSearchParams(location.search)).get("ws")
      || "ws://127.0.0.1:8765/ws";
}

const $ = (id) => document.getElementById(id);
const els = {};
[
  "zone","coords","severity",
  "playerName","playerSub","playerLevel","portraitIcon",
  "hpFill","hpVal","hpPct","mpFill","mpVal","mpPct","powerLabel",
  "xpFill","xpPct",
  "playerCast","playerCastSpell","playerCastFill",
  "comboPoints","restingTag","mountedTag","pvpTag","groupTag",
  "goldVal","bagVal","durVal",
  "buffStrip","debuffStrip",
  "targetName","targetSub","targetLevel","targetLabel",
  "targetVal","targetPct","targetFill",
  "targetCast","targetCastSpell","targetCastFill",
  "minimap","minimapZoneName","minimapCoords",
  "feed","status"
].forEach(k => els[k] = $(k));

// Optional override: combat log "engaged target name" wins over generic label.
let engagedName = null;

// Spell metadata DB (keeps cast bars showing real names + icons).
const SPELLS = new Map();   // id -> {name, icon, school, rank, castMs}

// ---------- Lookups ----------
const ZONE_NAMES = {
  0xD3DE: "Alterac Mountains",     0xC54B: "Arathi Highlands",
  0x1763: "Ashenvale",             0x9722: "Azshara",
  0x35E7: "Azuremyst Isle",        0x4F23: "Badlands",
  0xF2DF: "Blasted Lands",         0x3ADC: "Bloodmyst Isle",
  0xEF25: "Burning Steppes",       0xEE97: "Darkshore",
  0xE0E6: "Darnassus",             0xC145: "Deadwind Pass",
  0x5CD4: "Desolace",              0x5043: "Dun Morogh",
  0x6A37: "Durotar",               0x2377: "Dustwallow Marsh",
  0x5FDA: "Eastern Plaguelands",   0x3ED4: "Elwynn Forest",
  0x7439: "Eversong Woods",        0x6019: "Exodar",
  0x5B9A: "Felwood",               0xDB90: "Feralas",
  0x5ED9: "Ghostlands",            0x81C9: "Hillsbrad Foothills",
  0x36D4: "Hinterlands",           0xF37F: "Ironforge",
  0x41B7: "Loch Modan",            0xA31C: "Moonglade",
  0x3EBF: "Mulgore",               0x604C: "Orgrimmar",
  0xC7A0: "Redridge Mountains",    0xE247: "Searing Gorge",
  0x3105: "Silithus",              0x7EBD: "Silvermoon City",
  0x23A0: "Silverpine Forest",     0x0C9F: "Stonetalon Mountains",
  0xDBFA: "Stormwind City",        0x4AEF: "Stranglethorn Vale",
  0x2E66: "Swamp of Sorrows",      0x701C: "Tanaris",
  0x5F3B: "Teldrassil",            0x30DC: "The Barrens",
  0x3985: "The Hinterlands",       0xD682: "Thousand Needles",
  0x10EF: "Thunder Bluff",         0xA82C: "Tirisfal Glades",
  0xDB1C: "Un'Goro Crater",        0xD023: "Undercity",
  0xC7E8: "Western Plaguelands",   0x6DCA: "Westfall",
  0x7462: "Wetlands",              0x8532: "Winterspring",
};

const POWER_COLORS = {
  mana:   "#60a5fa",
  rage:   "#ef4444",
  energy: "#facc15",
  focus:  "#fb923c",
};

// Drop the entire ASCII portrait set in favor of class icons (icons.js).
const PORTRAITS_LEGACY = null;

// ---------- Helpers ----------
function setBarTier(fillEl, pct) {
  if (pct >= 60)      fillEl.dataset.tier = "good";
  else if (pct >= 30) fillEl.dataset.tier = "mid";
  else                fillEl.dataset.tier = "low";
}

function fmtNum(n) {
  if (n == null) return "—";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 10_000)    return (n / 1_000).toFixed(0) + "k";
  return n.toLocaleString();
}

function fmtGold(g) {
  if (!g) return "0";
  if (g >= 1000) return (g / 1000).toFixed(1) + "k";
  return String(g);
}

function zoneLabel(hash) {
  if (hash == null) return "—";
  return ZONE_NAMES[hash]
      || `zone#${hash.toString(16).toUpperCase().padStart(4, "0")}`;
}

// ---------- Player card ----------
function renderPlayer(p) {
  if (!p) return;
  els.playerName.textContent = (p.class && p.race)
    ? `${p.race.toUpperCase()} ${p.class.toUpperCase()}`
    : "PLAYER";
  els.playerSub.textContent =
    `${p.faction || "—"} · ${p.gender === "F" ? "Female" : "Male"}`;
  els.playerLevel.textContent = p.level || "?";

  const art = window.ICONS ? window.ICONS.iconForClass(p.class || "") : "";
  els.portraitIcon.innerHTML = art;
  els.portraitIcon.dataset.cls = (p.class || "?").toLowerCase();

  // HP
  if (p.hpMax != null) {
    const pct = p.hpPct ?? 0;
    els.hpFill.style.width = pct + "%";
    setBarTier(els.hpFill, pct);
    els.hpVal.textContent = `${fmtNum(p.hp)} / ${fmtNum(p.hpMax)}`;
    els.hpPct.textContent = pct + " %";
  }

  // MP / power
  if (p.mpMax != null) {
    const pct = p.mpPct ?? 0;
    els.mpFill.style.width = pct + "%";
    els.mpVal.textContent = `${fmtNum(p.mp)} / ${fmtNum(p.mpMax)}`;
    els.mpPct.textContent = pct + " %";
    const pwr = p.powerType || "mana";
    els.powerLabel.textContent = pwr.toUpperCase();
    els.mpFill.style.background = POWER_COLORS[pwr] || POWER_COLORS.mana;
  }

  // XP
  els.xpFill.style.width = (p.xpPct ?? 0) + "%";
  els.xpPct.textContent = (p.xpPct ?? 0) + (p.restedXp ? " % +RESTED" : " %");
  els.xpFill.dataset.rested = p.restedXp ? "1" : "0";

  // Combo points (rogue/druid)
  const combo = p.comboPoints || 0;
  els.comboPoints.textContent = "●●●●●".slice(0, combo) + "○○○○○".slice(0, 5 - combo);
  els.comboPoints.style.opacity = combo > 0 ? "1" : "0.25";

  // Tags
  els.restingTag.hidden = !p.resting;
  els.mountedTag.hidden = !p.mounted;
  els.pvpTag.hidden     = !p.pvp;
  els.groupTag.hidden   = !p.grouped;

  // Stats
  els.goldVal.textContent = fmtGold(p.gold);
  els.bagVal.textContent  = (p.bagFree != null ? p.bagFree : "—");
  els.durVal.textContent  = (p.durabilityPct != null ? p.durabilityPct + "%" : "—");
  if (p.bagFull) els.bagVal.classList.add("warn"); else els.bagVal.classList.remove("warn");
  if (p.durabilityPct != null && p.durabilityPct < 25) els.durVal.classList.add("warn");
  else els.durVal.classList.remove("warn");

  // Cast bar
  if (p.cast && p.cast.spellId) {
    els.playerCast.classList.add("active");
    renderCastInto(els.playerCastSpell, els.playerCastFill, p.cast);
  } else {
    els.playerCast.classList.remove("active");
  }
}

// ---------- Cast bar helper ----------
function renderCastInto(labelEl, fillEl, cast) {
  const meta = SPELLS.get(cast.spellId);
  const name = meta ? meta.name : `Spell #${cast.spellId}`;
  const rank = meta && meta.rank ? `  ${meta.rank}` : "";
  let icon = "";
  if (window.ICONS && meta) {
    icon = `<span class="cast-icon">${window.ICONS.iconForSpell(meta).svg}</span>`;
  }
  labelEl.innerHTML = `${icon}<span class="cast-name">${escapeHtml(name)}${escapeHtml(rank)}</span>`;
  fillEl.style.width = (cast.progress || 0) + "%";
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;" }[c]));
}

// ---------- Target card ----------
function renderTarget(t) {
  if (!t || !t.exists) {
    document.body.dataset.target = "0";
    els.targetName.textContent = "NO TARGET";
    els.targetSub.textContent = "—";
    els.targetLevel.textContent = "—";
    els.targetLevel.dataset.cls = "normal";
    els.targetLabel.textContent = "—";
    els.targetVal.textContent = "— / —";
    els.targetPct.textContent = "— %";
    els.targetFill.style.width = "0%";
    els.targetCast.classList.remove("active");
    return;
  }
  document.body.dataset.target = "1";
  els.targetName.textContent = (engagedName || (t.isPlayer ? "PLAYER" : "ENEMY")).toUpperCase();
  const tags = [];
  if (t.classification && t.classification !== "normal") tags.push(t.classification.toUpperCase());
  if (t.isPlayer) tags.push("PLAYER");
  els.targetSub.textContent = tags.join(" · ") || (t.hostile ? "HOSTILE" : "FRIENDLY");

  els.targetLevel.textContent = t.level || "?";
  els.targetLevel.dataset.cls = t.classification || "normal";

  els.targetLabel.textContent = t.hostile ? "HEALTH" : "ALLY";
  const pct = t.hpPct ?? 0;
  els.targetFill.style.width = pct + "%";
  els.targetFill.dataset.faction = t.hostile ? "hostile" : "friendly";
  els.targetVal.textContent = `${fmtNum(t.hp)} / ${fmtNum(t.hpMax)}`;
  els.targetPct.textContent = pct + " %";

  // Cast bar
  if (t.cast && t.cast.spellId) {
    els.targetCast.classList.add("active");
    renderCastInto(els.targetCastSpell, els.targetCastFill, t.cast);
  } else {
    els.targetCast.classList.remove("active");
  }
}

// ---------- Buff/debuff strips ----------
function renderAuras(parent, ids, kind) {
  parent.innerHTML = "";
  (ids || []).forEach(id => {
    if (!id) return;
    const meta = SPELLS.get(id);
    const cell = document.createElement("div");
    cell.className = "aura aura-" + kind;
    if (window.ICONS && meta) {
      const icon = window.ICONS.iconForSpell(meta);
      cell.innerHTML = icon.svg;
      cell.dataset.school = icon.school;
      cell.title = `${meta.name}${meta.rank ? " · " + meta.rank : ""}`;
    } else {
      cell.textContent = String(id).slice(-3);
      cell.title = `Spell #${id}`;
    }
    parent.appendChild(cell);
  });
}

// ---------- Minimap (player position) ----------
const MAP_W = 60, MAP_H = 22;
const TRAIL_LEN = 40;
let trailHistory = [];
let currentZoneHash = null;

function blankMap() {
  return Array.from({ length: MAP_H }, () => ".".repeat(MAP_W));
}

function renderMinimap(snap) {
  const z = snap.zone || {};
  const hash = z.hash;
  els.minimapZoneName.textContent = zoneLabel(hash).toUpperCase();

  if (hash !== currentZoneHash) {
    trailHistory = [];
    currentZoneHash = hash;
  }
  if (z.mapX == null) {
    els.minimap.textContent = blankMap().join("\n");
    els.minimapCoords.textContent = "";
    return;
  }
  const nx = z.mapX / 255, ny = z.mapY / 255;
  const col = Math.round(nx * (MAP_W - 1));
  const row = Math.round(ny * (MAP_H - 1));
  const last = trailHistory[trailHistory.length - 1];
  if (!last || last.col !== col || last.row !== row) {
    trailHistory.push({ col, row });
    if (trailHistory.length > TRAIL_LEN) trailHistory.shift();
  }
  const grid = blankMap().map(line => line.split(""));
  for (let i = 0; i < trailHistory.length - 1; i++) {
    const { col: tc, row: tr } = trailHistory[i];
    grid[tr][tc] = "·";
  }
  grid[row][col] = "@";
  els.minimap.textContent = grid.map(r => r.join("")).join("\n");
  els.minimapCoords.textContent = `${Math.round(nx * 100)},${Math.round(ny * 100)}`;
}

// ---------- Header / severity ----------
function renderHeader(snap) {
  const z = snap.zone || {};
  els.zone.textContent = zoneLabel(z.hash).toUpperCase();
  els.coords.textContent = (z.mapX != null)
    ? `(${Math.round((z.mapX/255)*100)}, ${Math.round((z.mapY/255)*100)})` : "";
  document.body.dataset.combat = snap.combat ? "1" : "0";
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
function setSeverity(level) {
  els.severity.dataset.level = String(level);
  els.severity.textContent = `SEV ${level}`;
  document.body.dataset.severity = String(level);
}
function setStatus(text, live) {
  els.status.textContent = text;
  els.status.classList.toggle("live", !!live);
}

// ---------- Feed ----------
function pushFeed(line, klass) {
  const div = document.createElement("div");
  div.className = "line" + (klass ? " " + klass : "");
  div.textContent = line;
  els.feed.appendChild(div);
  while (els.feed.childElementCount > 60) els.feed.firstElementChild.remove();
  els.feed.scrollTop = els.feed.scrollHeight;
}

// ---------- Event handler ----------
function handle(evt) {
  switch (evt.t) {
    case "snapshot": {
      const d = evt.data;
      renderHeader(d);
      renderPlayer(d.player);
      renderTarget(d.target);
      renderAuras(els.buffStrip, d.buffs, "buff");
      renderAuras(els.debuffStrip, d.debuffs, "debuff");
      renderMinimap(d);
      break;
    }
    case "spell_meta_bulk": {
      (evt.spells || []).forEach(s => SPELLS.set(s.id, s));
      break;
    }
    case "spell_meta": {
      SPELLS.set(evt.id, {
        id: evt.id, name: evt.name, icon: evt.icon,
        school: evt.school, rank: evt.rank, castMs: evt.castMs,
      });
      break;
    }
    case "action_bar": {
      // Action bar removed from UI; ignore (kept for backward-compat with addon).
      break;
    }
    case "engaged_target": {
      engagedName = evt.name;
      // Refresh just the target name without waiting for next snapshot.
      if (engagedName) els.targetName.textContent = engagedName.toUpperCase();
      break;
    }
    case "severity":
      setSeverity(evt.level);
      break;
    case "death":
      pushFeed(`*** ${evt.player} has died ***`, "death");
      break;
    case "combat":
      if (evt.event === "UNIT_DIED") pushFeed(`☠ ${evt.dst || "?"} dies.`, "death");
      break;
    case "combat_summary": {
      const arrow = evt.direction === "out" ? "→"
                  : evt.direction === "in"  ? "←" : "·";
      const who = evt.direction === "out" ? evt.dst : evt.src;
      const cls = evt.direction === "in" ? "in" : "out";
      const hits = evt.count > 1 ? ` x${evt.count}` : "";
      const total = evt.total ? ` (${evt.total})` : "";
      pushFeed(`${arrow} ${evt.spell || evt.event}${hits}${total} ${who || ""}`.trim(), cls);
      break;
    }
  }
}

function connect() {
  const url = _resolveWsUrl();
  setStatus(`connecting ${url}…`, false);
  const ws = new WebSocket(url);
  ws.onopen    = () => setStatus("LIVE", true);
  ws.onclose   = () => { setStatus("disconnected — retrying", false); setTimeout(connect, 2000); };
  ws.onerror   = () => { try { ws.close(); } catch (_) {} };
  ws.onmessage = (m) => { try { handle(JSON.parse(m.data)); } catch (e) { console.error(e); } };
}

renderHeader({});
renderPlayer({});
renderTarget(null);
renderMinimap({});

// Auto-connect only when running standalone (OBS browser source). The Twitch
// extension viewer.js sets window.ASCIIMUD_DEFER_CONNECT=true before this
// script loads and calls window.ASCIIMUD_connect() after auth.
window.ASCIIMUD_connect = connect;
if (!window.ASCIIMUD_DEFER_CONNECT) connect();
