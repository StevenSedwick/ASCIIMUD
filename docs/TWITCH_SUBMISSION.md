# Twitch Extension Submission — ASCIIMUD

End-to-end checklist for getting the ASCIIMUD video overlay extension reviewed
and live on Twitch. Do these in order.

## 0. Prerequisites

- A Twitch account with **Two-Factor Authentication** and a verified phone
  number — both are required to register an extension.
- A deployed Cloudflare Worker EBS (see [`../ebs/README.md`](../ebs/README.md)).
  - **This deployment:** `https://asciimud-ebs.goreakis2.workers.dev`
- The companion app running locally and successfully POSTing to that Worker
  (i.e. `[twitch] ebs_url` set in `companion/config.toml`).

## 1. Create the extension shell

1. Visit <https://dev.twitch.tv/console/extensions/create>.
2. **Name:** ASCIIMUD (or whatever you wish — must be unique on Twitch).
3. **Type:** Video — Overlay.
4. **Description (short, ≤200 chars):** *"A theatrical ASCII heads-up display
   that overlays the streamer's WoW Classic adventure on the video feed."*
5. **Description (long):** A few paragraphs covering: what viewers will see,
   why the overlay shows ASCII art (the streamer is in a blacked-out, screen-
   reader-style mode), the toggle button, the fact that no chat or identity
   permissions are requested.

## 2. Capabilities & permissions

In the **Capabilities** tab:

- **Anchors:** `Video Overlay`. Leave Component, Panel, and Mobile **unchecked**.
- **Allowed origins for testing:** add your local dev URL (e.g.
  `http://localhost:8123`) and your Worker URL.
- **Configuration Service:** **enabled** (we use the broadcaster segment to
  store the EBS URL).
- **Identity link:** **disabled** (we do not need the viewer's identity).
- **Chat capabilities:** **none**.
- **Subscription support:** **none**.

The lighter the permission ask, the faster the review.

## 3. Asset checklist

In **Asset Hosting**, upload:

| Asset                  | Spec              | Notes                                |
| ---------------------- | ----------------- | ------------------------------------ |
| Discovery icon         | 100×100 PNG       | Big "A" glyph on dark background.    |
| Small discovery icon   | 24×24 PNG         | Same glyph, simplified.              |
| Screenshot 1           | 1280×720 PNG/JPG  | Overlay expanded over a stream.      |
| Screenshot 2 (opt.)    | 1280×720          | Overlay collapsed (toggle visible).  |
| Screenshot 3 (opt.)    | 1280×720          | Configuration panel.                 |

Place source assets in `twitch-ext/assets/` and reference them from this doc.

## 4. Files & paths

- **Viewer Path:** `viewer.html`
- **Configuration Path:** `config.html`
- **Live Configuration Path:** *(blank — we don't have a live config view)*
- **Mobile path:** *(blank)*
- **Testing Base URI:** `https://your-test-host.example.com/` (for hosted
  testing; you can use GitHub Pages, Cloudflare Pages, or any HTTPS host
  during the testing phase).

## 5. Required URLs

Reviewers require these to be reachable HTTPS URLs:

- **Privacy Policy:** Host `docs/privacy.md` somewhere public (GitHub Pages
  works fine: enable Pages on the repo and use the rendered URL).
- **Terms of Service:** Same idea with `docs/terms.md`.
- **Support email:** A real address you read.

## 6. Build & upload

```pwsh
cd twitch-ext
./build.ps1   # produces dist/asciimud-twitch-ext.zip
```

Upload the zip in **Files → Asset Hosting** for the version under review.

## 7. Hosted-test on your own channel

1. In **Status**, move the version to **Hosted Test**.
2. Open the **Test** tab and copy the install link.
3. On your channel's Extensions page, install the extension and activate it
   as a video overlay.
4. Start streaming, open the channel in another browser, and confirm:
   - Toggle button appears in the bottom-right.
   - Clicking it expands the overlay.
   - Snapshots arrive within ~1 second of in-game changes.

## 8. Submit for review

When everything works in hosted-test mode:

1. **Status → Submit for Review.**
2. Fill out the reviewer questionnaire (especially: confirm no PII is
   transmitted to the EBS; confirm the JWT is HS256-verified server-side).
3. Wait. Initial review typically takes 5–10 business days.

## Common rejection reasons we have already addressed

- ✅ Transparent body background (extension iframes must not have an opaque
  background that obscures the stream).
- ✅ `pointer-events: none` on the body so clicks pass through to the video.
- ✅ Toggle button so viewers can hide the overlay if they prefer.
- ✅ JWT verification on the WebSocket upgrade — viewers cannot connect to
  an arbitrary channel's data stream.
- ✅ Configuration view validates the EBS URL format.
