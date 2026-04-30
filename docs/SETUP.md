# ASCIIMUD Setup

## 1. Install the addon

Copy (or symlink) the `addon/` directory into your WoW install as
`Interface/AddOns/ASCIIMUD`:

```
World of Warcraft\_classic_era_\Interface\AddOns\ASCIIMUD\
    ASCIIMUD.toc
    core\ render\ systems\ stream\ libs\
```

Launch WoW. At the character select screen, enable **ASCIIMUD** in the AddOns
menu. On first login the addon enables `/chatlog` automatically.

In-game commands:

- `/mud` or `/mud toggle` — toggle the veil (show/hide WoW UI)
- `/mud off` — restore the standard WoW UI
- `/mud on`  — re-enable the ASCIIMUD veil

## 2. Run the companion

```powershell
cd companion
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.example.toml config.toml
# edit config.toml: point log_path at your WoWChatLog.txt
python companion.py
```

You should see:

```
... INFO asciimud.companion WebSocket server on ws://127.0.0.1:8765/ws
... INFO asciimud.companion Tailing C:\...\WoWChatLog.txt
```

## 3. Add the OBS browser source

In OBS, add a **Browser** source pointing at the local `overlay/index.html`:

- **URL:** `file:///C:/path/to/ASCIIMUD/overlay/index.html`
- **Width:** 1920, **Height:** 1080
- Check **Refresh browser when scene becomes active**.

The overlay connects to `ws://127.0.0.1:8765/ws` by default. To override:

```
file:///.../overlay/index.html?ws=ws://192.168.1.20:8765/ws
```

## 4. Verify

1. Log in to your character.
2. Move, take damage, target a mob.
3. Watch the OBS preview update in real time.

If the overlay says "disconnected — retrying", the companion isn't running or
the WS port is blocked.
