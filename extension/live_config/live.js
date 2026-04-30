// Broadcaster-side live dashboard. Polls /healthz and /config/digest.
const $ = (id) => document.getElementById(id);
let ebs = null, token = null, channelId = null;

window.Twitch.ext.onAuthorized(async (auth) => {
  token = auth.token;
  channelId = auth.channelId;
  $("ch").textContent = channelId;

  const seg = window.Twitch.ext.configuration.broadcaster;
  if (seg && seg.content) {
    try { ebs = JSON.parse(seg.content).ebs || null; } catch (_) {}
  }
  $("ebs").textContent = ebs || "(unset — open Configure)";
  if (ebs) tick();
});

async function tick() {
  try {
    const [health, digest] = await Promise.all([
      fetch(`https://${ebs}/healthz`).then(r => r.json()),
      fetch(`https://${ebs}/config/digest?token=${encodeURIComponent(token)}`).then(r => r.json()),
    ]);
    const v = (health.viewers || {})[channelId] ?? 0;
    $("viewers").textContent = v;
    $("last").textContent = digest && digest.ts
      ? new Date(digest.ts * 1000).toLocaleTimeString()
      : "(no events yet)";
  } catch (e) {
    $("last").textContent = `error: ${e.message}`;
  }
  setTimeout(tick, 2000);
}
