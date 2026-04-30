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
  minimap: $("minimap"),
  minimapZoneName: $("minimapZoneName"),
  minimapCoords: $("minimapCoords"),
  feed: $("feed"),
  status: $("status"),
};

// ---------- Zone name lookup (FNV-1a 16-bit of GetZoneText()) ----------
const ZONE_NAMES = {
  0xFB88: "Dun Morogh",
  0x17FD: "Elwynn Forest",
  0x390C: "Teldrassil",
  0x53C4: "Durotar",
  0x46DE: "Mulgore",
  0x013F: "Tirisfal Glades",
  0x274B: "Stormwind City",
  0x6D5A: "Ironforge",
  0x77E3: "Darnassus",
  0xE6C5: "Orgrimmar",
  0x2DE4: "Thunder Bluff",
  0xAC6A: "Undercity",
  0xBBA7: "The Barrens",
  0x25FB: "Westfall",
  0xC6F0: "Loch Modan",
  0x85EB: "Redridge Mountains",
  0x4A32: "Darkshore",
  0x771E: "Ashenvale",
  0x7ACA: "Hillsbrad Foothills",
  0x9BEB: "Wetlands",
  0x7D02: "Arathi Highlands",
  0x8393: "Silverpine Forest",
  0xB66A: "Stonetalon Mountains",
  0xCD97: "Desolace",
  0x32D7: "Thousand Needles",
  0xCCAB: "Feralas",
  0xF0AF: "Tanaris",
  0x9631: "Un'Goro Crater",
  0x171E: "Silithus",
  0xFEF3: "Eastern Plaguelands",
  0x713D: "Western Plaguelands",
  0xE409: "Winterspring",
  0xE8E5: "Azshara",
  0x653D: "Felwood",
  0x9B71: "Moonglade",
  0xFBE6: "Deadwind Pass",
  0x7803: "Alterac Mountains",
  0xA3CA: "Badlands",
  0x615E: "Burning Steppes",
  0xA332: "Searing Gorge",
  0xEB05: "Swamp of Sorrows",
  0x51B2: "Blasted Lands",
  0xBA0C: "Dustwallow Marsh",
  0xB4AE: "Stranglethorn Vale",
  0xBA63: "Hinterlands",
};

// ---------- Zone ASCII art maps (40 wide × 14 tall) ----------
// Legend: . open  # mountain/wall  ~ water  ^ forest  * town  = road
// Player '@' and trail '·' are overlaid at runtime using mapX/mapY (0-255).
const MAP_W = 40, MAP_H = 14;

const ZONE_MAPS = {
  0xFB88: [ // Dun Morogh
    "########################################",
    "#####^^^############################^^^^",
    "####^^^^^###########^^^^##########^^^^^^",
    "##^^^^^^^##~~~~~##^^^^^##########^^^^^^^",
    "#^^^^^^^^^#~~~~~#^^^^^^^^^^^^^^^^*ironf*",
    "##^^^^^^^^^######^^^^^^^^^^^^^^^^=======",
    "####^^^^^^^^^^^^^^^^^^*kharanos*========",
    "#####^^^^^^^^^^^^^^^^^==================",
    "######^^^^^^^^^.......==================",
    "########^^^^^^^.......====*steelgrill*==",
    "##########^^^^^.......==================",
    "############^^^^^^^^.....===============",
    "##############^^^^^^^^^.................",
    "####################^^^^################",
  ],
  0x17FD: [ // Elwynn Forest
    "........................................",
    ".....*stormwind*........................",
    "........========================........",
    "...^^^..========================..^^^...",
    "..^^^^^.=====.........==========.^^^^^..",
    ".^^^^^^^=====...*goldshire*.=====.^^^^^.",
    "..^^^^^^=====...............=====.^^^^^.",
    "...^^^^^=====...............=====.......",
    "....^^^..====...............=====.......",
    ".....^...====...~~lakeshire~=====.......",
    "..........===...~~~~~~~~~~~~~~~~~~~~~...",
    "...........==...........................",
    "............============================",
    "........................................",
  ],
  0x53C4: [ // Durotar
    "........................................",
    "....*orgrimmar*..........................",
    "...........=====================........",
    "..#........=====================.......#",
    ".###.......=====================......##",
    "..##.......=====.......=====..........##",
    "...#.......=====.......=====.........###",
    "....#......=====.......=====.........###",
    ".....#.....=====..*.....====........####",
    "......#....=====.......=====.......#####",
    ".......####============#####......######",
    "........####..........######.....#######",
    ".........######.....########....########",
    "################....#######################",
  ],
  0x46DE: [ // Mulgore
    "........................................",
    "...####..................................",
    "..######..............*thunder bluff*...",
    "..######..^^...........................",
    ".########.^^^..........................",
    "..########.^^......*camp narache*......",
    "...######...................................",
    "....######..................................",
    ".....######.................................",
    "......######.......*bloodhoof village*......",
    ".......#####################################",
    "........####################################",
    ".........###################################",
    "..........##################################",
  ],
  0x013F: [ // Tirisfal Glades
    "~~~~~~~~~~~~~~~~~~~~####################",
    "~~~~~~~~~~~~~~~~~~~~####################",
    "~~~~~~~~~~~~~~~~~~~~^^^#################",
    "~~~~~~~~~~~~~~~~~~~~^^^###^^^###########",
    "~~~~~~~~~~~~~*.undercity*.^^^###########",
    "..............===========.^^^###########",
    "...............==========.^^^###########",
    "................=========..^^###########",
    ".................========..^^###########",
    "..................=======...^############",
    "...................======....############",
    "....*brill*..........====....###########",
    ".....................................####",
    "........................................",
  ],
  0xBBA7: [ // The Barrens
    "........................................",
    "...#.....................................",
    "..##....*crossroads*....................",
    ".###....========================........",
    ".###....========================........",
    ".###....====....................",
    "..##....====.....*camp taurajo*.",
    "...#....====.....................",
    "....#...====.....................",
    ".....#..====.....................",
    "......##====.....................",
    ".......#====..~razorfen~.........",
    ".......#====..~~~~~~~~~..........",
    "........####......................",
  ],
  0x25FB: [ // Westfall
    "........................................",
    "........................................",
    "......*sentinel hill*....................",
    ".......=========================........",
    "..^^^^^=========================..^^^^^.",
    "..^^^^^=====.............=======..^^^^^.",
    "..^^^^^=====.............=======..^^^^^.",
    "..^^^^^=====.............=======..^^^^^.",
    "..^^^^^=====.............=======..^^^^^.",
    "..^^^^^=====.............=======..^^^^^.",
    "~~~~~~~~====.............=======~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~.....~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
  ],
};

// ---------- Minimap state ----------
const TRAIL_LEN = 20;
let trailHistory = [];   // [{x,y}] recent positions (normalised 0-1)
let currentZoneHash = null;

function getZoneMap(hash) {
  return ZONE_MAPS[hash] || null;
}

function renderMinimap(snap) {
  const z = snap.zone || {};
  const hash = z.hash;
  const mapX = z.mapX;  // 0-255
  const mapY = z.mapY;  // 0-255

  const zoneName = ZONE_NAMES[hash]
    || (hash != null ? `zone#${hash.toString(16).toUpperCase().padStart(4,"0")}` : "—");
  els.minimapZoneName.textContent = zoneName.toUpperCase();

  // Reset trail when zone changes.
  if (hash !== currentZoneHash) {
    trailHistory = [];
    currentZoneHash = hash;
  }

  if (mapX == null || mapY == null) {
    els.minimap.textContent = blankMap().join("\n");
    els.minimapCoords.textContent = "";
    return;
  }

  const nx = mapX / 255;
  const ny = mapY / 255;
  const col = Math.round(nx * (MAP_W - 1));
  const row = Math.round(ny * (MAP_H - 1));

  // Add to trail (deduplicate consecutive same position).
  const last = trailHistory[trailHistory.length - 1];
  if (!last || last.col !== col || last.row !== row) {
    trailHistory.push({ col, row });
    if (trailHistory.length > TRAIL_LEN) trailHistory.shift();
  }

  // Build map grid.
  const art = getZoneMap(hash);
  const grid = (art || blankMap()).map(line => line.split(""));

  // Draw trail dots (skip if occupied by player pos).
  for (let i = 0; i < trailHistory.length - 1; i++) {
    const { col: tc, row: tr } = trailHistory[i];
    if (tr >= 0 && tr < MAP_H && tc >= 0 && tc < MAP_W) {
      grid[tr][tc] = "·";
    }
  }

  // Draw player.
  if (row >= 0 && row < MAP_H && col >= 0 && col < MAP_W) {
    grid[row][col] = "@";
  }

  els.minimap.textContent = grid.map(r => r.join("")).join("\n");
  els.minimapCoords.textContent = `${Math.round(nx * 100)},${Math.round(ny * 100)}`;
}

function blankMap() {
  return Array.from({ length: MAP_H }, () => ".".repeat(MAP_W));
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

  // Zone label in the top header strip.
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
      renderMinimap(evt.data);
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

renderMinimap({});
renderHeader({ player: {}, zone: {} });
connect();
