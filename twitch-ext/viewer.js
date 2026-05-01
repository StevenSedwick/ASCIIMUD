// ASCIIMUD — Twitch extension viewer bootstrap.
//
// Resolves the EBS WebSocket URL from broadcaster config (set in config.html)
// and connects after Twitch.ext.onAuthorized fires. Provides a collapse/expand
// toggle button so viewers can hide the overlay if they prefer.

(function () {
  "use strict";

  const TOGGLE_KEY = "asciimud:expanded";
  const body = document.body;
  const toggleBtn = document.getElementById("txToggle");

  // ---- collapse / expand ----------------------------------------------------
  function applyCollapsed(collapsed) {
    body.classList.toggle("tx-collapsed", collapsed);
    body.classList.toggle("tx-expanded", !collapsed);
    try { localStorage.setItem(TOGGLE_KEY, collapsed ? "0" : "1"); } catch (_) {}
  }

  let initialExpanded = false;
  try { initialExpanded = localStorage.getItem(TOGGLE_KEY) === "1"; } catch (_) {}
  applyCollapsed(!initialExpanded);

  toggleBtn.addEventListener("click", function () {
    applyCollapsed(!body.classList.contains("tx-collapsed"));
  });

  // ---- Twitch helper --------------------------------------------------------
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
