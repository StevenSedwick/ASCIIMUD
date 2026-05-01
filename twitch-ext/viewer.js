// ASCIIMUD — Twitch extension viewer bootstrap.
//
// Resolves the EBS WebSocket URL from broadcaster config (set in config.html)
// and connects after Twitch.ext.onAuthorized fires. The widget card supports
// compact/expanded toggle (click header) and free drag-to-reposition.

(function () {
  "use strict";

  const TOGGLE_KEY = "asciimud:expanded";
  const POS_X_KEY  = "asciimud:pos:x";
  const POS_Y_KEY  = "asciimud:pos:y";

  const body   = document.body;
  const widget = document.getElementById("widget");
  const header = document.getElementById("widgetHeader");
  const chevron = document.getElementById("widgetChevron");

  // ── Collapse / expand ──────────────────────────────────────────────────────
  function applyExpanded(expanded) {
    body.classList.toggle("tx-expanded",  expanded);
    body.classList.toggle("tx-collapsed", !expanded);
    chevron.textContent = expanded ? "▲" : "▼";
    try { localStorage.setItem(TOGGLE_KEY, expanded ? "1" : "0"); } catch (_) {}
  }

  // Restore saved preference; default collapsed
  let initialExpanded = false;
  try { initialExpanded = localStorage.getItem(TOGGLE_KEY) === "1"; } catch (_) {}
  applyExpanded(initialExpanded);

  // ── Drag to reposition ─────────────────────────────────────────────────────
  let dragging   = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let dragOrigL  = 0;
  let dragOrigT  = 0;

  function getWidgetRect() {
    return widget.getBoundingClientRect();
  }

  function clampPos(x, y) {
    const w   = widget.offsetWidth  || 280;
    const h   = widget.offsetHeight || 200;
    const vw  = window.innerWidth;
    const vh  = window.innerHeight;
    return {
      x: Math.max(0, Math.min(x, vw - w)),
      y: Math.max(0, Math.min(y, vh - h)),
    };
  }

  function setWidgetPos(x, y) {
    widget.style.left   = x + "px";
    widget.style.top    = y + "px";
    widget.style.bottom = "auto";
    widget.style.right  = "auto";
  }

  function savePos() {
    const r = getWidgetRect();
    try {
      localStorage.setItem(POS_X_KEY, String(Math.round(r.left)));
      localStorage.setItem(POS_Y_KEY, String(Math.round(r.top)));
    } catch (_) {}
  }

  // Restore saved position (if any); otherwise CSS bottom/left defaults take effect
  (function restorePos() {
    try {
      const sx = localStorage.getItem(POS_X_KEY);
      const sy = localStorage.getItem(POS_Y_KEY);
      if (sx !== null && sy !== null) {
        const clamped = clampPos(parseInt(sx, 10), parseInt(sy, 10));
        setWidgetPos(clamped.x, clamped.y);
      }
    } catch (_) {}
  })();

  header.addEventListener("mousedown", function (e) {
    // Don't start drag on right-click
    if (e.button !== 0) return;
    e.preventDefault();

    dragging   = true;
    dragStartX = e.clientX;
    dragStartY = e.clientY;

    const r  = getWidgetRect();
    dragOrigL = r.left;
    dragOrigT = r.top;

    header.style.cursor = "grabbing";
    document.body.style.userSelect = "none";
  });

  document.addEventListener("mousemove", function (e) {
    if (!dragging) return;
    const dx = e.clientX - dragStartX;
    const dy = e.clientY - dragStartY;
    const clamped = clampPos(dragOrigL + dx, dragOrigT + dy);
    setWidgetPos(clamped.x, clamped.y);
  });

  document.addEventListener("mouseup", function (e) {
    if (!dragging) return;
    dragging = false;
    header.style.cursor = "";
    document.body.style.userSelect = "";

    // Only toggle expand if mouse barely moved (click, not drag)
    const dx = Math.abs(e.clientX - dragStartX);
    const dy = Math.abs(e.clientY - dragStartY);
    if (dx < 4 && dy < 4) {
      applyExpanded(body.classList.contains("tx-collapsed"));
    } else {
      savePos();
    }
  });

  // ── ASCII block bar helper (drives hpBar, mpBar, xpBar, targetBar, playerCastBar) ──
  // app.js sets fill% on #hpFill etc via style.width — we intercept those writes
  // and instead update the visible ASCII bar siblings.
  const BAR_LEN = 10;
  function makeAsciiBar(pct) {
    const filled = Math.round((pct / 100) * BAR_LEN);
    const empty  = BAR_LEN - filled;
    return "█".repeat(Math.max(0, filled)) + '<span class="e">' + "░".repeat(Math.max(0, empty)) + "</span>";
  }

  // Map from fill-div IDs → ascii bar element IDs
  const BAR_MAP = {
    hpFill:         "hpBar",
    mpFill:         "mpBar",
    xpFill:         "xpBar",
    targetFill:     "targetBar",
    playerCastFill: "playerCastBar",
  };
  // Intercept app.js writing style.width on fill divs
  Object.keys(BAR_MAP).forEach(function(fillId) {
    const fillEl = document.getElementById(fillId);
    const barEl  = document.getElementById(BAR_MAP[fillId]);
    if (!fillEl || !barEl) return;
    // Observe attribute mutations
    const obs = new MutationObserver(function() {
      const w = parseFloat(fillEl.style.width) || 0;
      barEl.innerHTML = makeAsciiBar(w);
    });
    obs.observe(fillEl, { attributes: true, attributeFilter: ["style"] });
  });

  // ── Twitch helper ──────────────────────────────────────────────────────────
  if (typeof Twitch === "undefined" || !Twitch.ext) {
    console.warn("[ASCIIMUD] Twitch helper not loaded — running in fallback dev mode.");
    window.ASCIIMUD_WS_URL = window.ASCIIMUD_WS_URL || "ws://127.0.0.1:8765/ws";
    window.ASCIIMUD_connect && window.ASCIIMUD_connect();
    return;
  }

  // Broadcaster config is JSON: { ebs_url: "https://...workers.dev" }
  function readBroadcasterConfig() {
    try {
      const seg = Twitch.ext.configuration.broadcaster;
      if (!seg || !seg.content) return null;
      return JSON.parse(seg.content);
    } catch (e) {
      console.warn("[ASCIIMUD] bad broadcaster config:", e);
      return null;
    }
  }

  function buildWsUrl(ebsUrl, channelId, token) {
    // ebsUrl is https://… → wss://… ; http://… → ws://… for local dev
    const wsBase = ebsUrl.replace(/^http/, "ws").replace(/\/+$/, "");
    return `${wsBase}/ws/${encodeURIComponent(channelId)}?jwt=${encodeURIComponent(token)}`;
  }

  let connected = false;

  function tryConnect(auth) {
    if (connected) return;
    const cfg = readBroadcasterConfig();
    if (!cfg || !cfg.ebs_url) {
      console.info("[ASCIIMUD] broadcaster has not configured ebs_url yet.");
      return;
    }
    window.ASCIIMUD_WS_URL = buildWsUrl(cfg.ebs_url, auth.channelId, auth.token);
    connected = true;
    window.ASCIIMUD_connect && window.ASCIIMUD_connect();
  }

  let lastAuth = null;
  Twitch.ext.onAuthorized(function (auth) {
    lastAuth = auth;
    tryConnect(auth);
  });
  Twitch.ext.configuration.onChanged(function () {
    if (lastAuth) tryConnect(lastAuth);
  });
})();
