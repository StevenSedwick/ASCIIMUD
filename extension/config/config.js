// Broadcaster-only config UI. Persists settings to the EBS.
const $ = (id) => document.getElementById(id);
let token = null;

function setStatus(s) { $("status").textContent = s; }

window.Twitch.ext.onAuthorized((auth) => {
  token = auth.token;
  $("save").disabled = false;
  setStatus("authorized — fetching current config…");

  // Pre-fill from broadcaster config segment if present.
  const seg = window.Twitch.ext.configuration.broadcaster;
  if (seg && seg.content) {
    try {
      const cfg = JSON.parse(seg.content);
      $("ebs").value = cfg.ebs || "";
      $("display").value = cfg.display || "";
    } catch (_) {}
  }
  setStatus("ready.");
});

$("save").addEventListener("click", async () => {
  const cfg = {
    ebs: $("ebs").value.trim(),
    display: $("display").value.trim(),
  };
  if (!cfg.ebs) { setStatus("EBS hostname is required."); return; }

  // 1. Save to Twitch's broadcaster configuration segment (so the viewer
  //    frontend can read it without a round trip to our EBS).
  window.Twitch.ext.configuration.set("broadcaster", "1", JSON.stringify(cfg));

  // 2. Tell our EBS too (so it can pre-warm any per-channel state).
  try {
    const resp = await fetch(`https://${cfg.ebs}/config/save`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`,
      },
      body: JSON.stringify(cfg),
    });
    setStatus(resp.ok ? "saved." : `EBS responded ${resp.status}`);
  } catch (e) {
    setStatus(`saved locally; EBS unreachable: ${e.message}`);
  }
});
