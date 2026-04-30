/* ASCIIMUD viewer — Twitch extension overlay/component frontend.
 *
 * Receives state via Twitch PubSub broadcast (1Hz digest) by default.
 * If the extension config provides an EBS URL, opts in to the rich WSS stream.
 */
(function () {
  const PUBSUB_TARGET = "broadcast";
  const els = {
    zone: document.getElementById("zone"),
    sev: document.getElementById("sev"),
    hpFill: document.getElementById("hpFill"),
    hpPct: document.getElementById("hpPct"),
    mpFill: document.getElementById("mpFill"),
    mpPct: document.getElementById("mpPct"),
    targetCard: document.getElementById("targetCard"),
    targetLabel: document.getElementById("targetLabel"),
    tgtFill: document.getElementById("tgtFill"),
    tgtPct: document.getElementById("tgtPct"),
    status: document.getElementById("status"),
  };

  let ebsUrl = null;
  let token  = null;
  let viewerWs = null;

  function setBarTier(fillEl, pct) {
    if (pct >= 60)      fillEl.dataset.tier = "good";
    else if (pct >= 30) fillEl.dataset.tier = "mid";
    else                fillEl.dataset.tier = "low";
  }

  function applyDigest(d) {
    els.zone.textContent = (d.z || "—").toUpperCase();
    els.sev.dataset.level = String(d.sev || 0);
    els.sev.textContent = `SEV ${d.sev || 0}`;
    document.body.dataset.combat = d.combat ? "1" : "0";

    if (d.hpPct != null) {
      els.hpFill.style.width = d.hpPct + "%";
      setBarTier(els.hpFill, d.hpPct);
      els.hpPct.textContent = d.hpPct + " %";
    }
    if (d.mpPct != null) {
      els.mpFill.style.width = d.mpPct + "%";
      els.mpPct.textContent = d.mpPct + " %";
    }
    if (d.tgtHpPct != null) {
      document.body.dataset.target = "1";
      els.targetLabel.textContent = d.tgtHostile ? "HOSTILE" : "FRIENDLY";
      els.tgtPct.textContent = d.tgtHpPct + " %";
      els.tgtFill.style.width = d.tgtHpPct + "%";
      els.tgtFill.dataset.faction = d.tgtHostile ? "hostile" : "friendly";
    } else {
      document.body.dataset.target = "0";
      els.targetLabel.textContent = "NO TARGET";
      els.tgtPct.textContent = "— %";
      els.tgtFill.style.width = "0%";
    }
  }

  function applyRich(evt) {
    if (evt.t === "snapshot") {
      const s = evt.data;
      const z = s.zone || {};
      const p = s.player || {};
      const t = s.target;
      applyDigest({
        z: z.name || (z.hash != null ? `zone#${z.hash.toString(16).toUpperCase().padStart(4,"0")}` : ""),
        hpPct: p.hpPct, mpPct: p.mpPct,
        combat: s.combat,
        tgtHpPct: t && t.exists ? t.hpPct : null,
        tgtHostile: t && t.hostile,
        sev: 0,
      });
    } else if (evt.t === "severity") {
      els.sev.dataset.level = String(evt.level || 0);
      els.sev.textContent = `SEV ${evt.level || 0}`;
    }
  }

  function connectViewerWs() {
    if (!ebsUrl || !token || viewerWs) return;
    const wsUrl = ebsUrl.replace(/^http/, "ws") + "/viewer?token=" + encodeURIComponent(token);
    els.status.textContent = "rich: connecting…";
    try {
      viewerWs = new WebSocket(wsUrl);
    } catch (_) { return; }
    viewerWs.onopen    = () => { els.status.textContent = "LIVE"; els.status.classList.add("live"); };
    viewerWs.onmessage = (m) => { try { applyRich(JSON.parse(m.data)); } catch (_) {} };
    viewerWs.onclose   = () => {
      viewerWs = null; els.status.classList.remove("live");
      els.status.textContent = "rich: disconnected, retrying";
      setTimeout(connectViewerWs, 2500);
    };
    viewerWs.onerror   = () => { try { viewerWs.close(); } catch (_) {} };
  }

  /* ------------------------- Twitch helper hooks ------------------------- */
  window.Twitch.ext.onAuthorized(function (auth) {
    token = auth.token;
    els.status.textContent = "authorized";
    if (ebsUrl) connectViewerWs();
  });

  window.Twitch.ext.configuration.onChanged(function () {
    const cfg = window.Twitch.ext.configuration.broadcaster;
    if (cfg && cfg.content) {
      try {
        const obj = JSON.parse(cfg.content);
        ebsUrl = obj.ebsUrl || null;
        if (token && ebsUrl) connectViewerWs();
      } catch (_) {}
    }
  });

  window.Twitch.ext.listen(PUBSUB_TARGET, function (target, contentType, message) {
    try {
      applyDigest(JSON.parse(message));
    } catch (e) {
      console.error("bad digest", e);
    }
  });
})();
