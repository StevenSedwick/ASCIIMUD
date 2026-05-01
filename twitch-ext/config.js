// ASCIIMUD — broadcaster configuration page.
// Stores { ebs_url } in Twitch broadcaster configuration segment.

(function () {
  "use strict";

  const ebsInput = document.getElementById("ebsUrl");
  const saveBtn  = document.getElementById("saveBtn");
  const status   = document.getElementById("saveStatus");

  function setStatus(msg, ok) {
    status.textContent = msg;
    status.style.color = ok ? "#7ee787" : "#ffa657";
  }

  function loadCurrent() {
    try {
      const seg = Twitch.ext.configuration.broadcaster;
      if (seg && seg.content) {
        const cfg = JSON.parse(seg.content);
        if (cfg.ebs_url) ebsInput.value = cfg.ebs_url;
      }
    } catch (e) {
      console.warn("[ASCIIMUD config] could not parse current config:", e);
    }
  }

  Twitch.ext.onAuthorized(function () {
    loadCurrent();
  });

  Twitch.ext.configuration.onChanged(function () {
    loadCurrent();
  });

  saveBtn.addEventListener("click", function () {
    const url = ebsInput.value.trim().replace(/\/+$/, "");
    if (!/^https?:\/\//i.test(url)) {
      setStatus("URL must start with https:// (or http:// for local dev).", false);
      return;
    }
    const payload = JSON.stringify({ ebs_url: url, v: 1 });
    try {
      Twitch.ext.configuration.set("broadcaster", "1", payload);
      setStatus("Saved. Viewers will pick up the change on next page load.", true);
    } catch (e) {
      setStatus("Save failed: " + e.message, false);
    }
  });
})();
