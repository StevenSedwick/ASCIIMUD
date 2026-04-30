"""Quick end-to-end smoke test against the running companion."""
import asyncio, json, aiohttp
from pathlib import Path


async def main():
    log = Path("C:/Program Files (x86)/World of Warcraft/_classic_era_/Logs/WoWChatLog.txt")
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect("ws://127.0.0.1:8765/ws") as ws:
            await asyncio.sleep(0.3)
            evt = {
                "t": "snapshot",
                "data": {
                    "v": 1, "tick": 2, "combat": True, "chapter": 1,
                    "player": {"name": "SmokeTest", "level": 99, "hp": 123,
                               "hpMax": 500, "mp": 100, "mpMax": 100},
                    "zone": {"name": "Stormwind", "subzone": "Trade District"},
                    "target": {"name": "TestMob", "hp": 50, "hpMax": 100,
                               "hostile": True, "level": 50},
                },
            }
            with log.open("a", encoding="utf-8") as f:
                f.write(f"4/30  ASCIIMUD|{json.dumps(evt)}\n")
            for i in range(5):
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=1.5)
                    if msg.type.name == "TEXT":
                        d = json.loads(msg.data)
                        if d.get("t") == "snapshot":
                            p = d["data"]["player"]
                            t = d["data"]["target"]
                            print(f"SNAPSHOT OK: hp={p['hp']} target={t['name']}")
                            return
                        else:
                            print(f"  (got {d.get('t')})")
                except asyncio.TimeoutError:
                    print("  timeout")
            print("FAIL: no snapshot received")


asyncio.run(main())
