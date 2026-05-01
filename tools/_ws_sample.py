import asyncio, aiohttp, json, time
from collections import Counter

async def t():
    types = Counter()
    samples = []
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect("ws://127.0.0.1:8765/ws", timeout=3) as ws:
            t0 = time.time()
            while time.time() - t0 < 8:
                try:
                    m = await asyncio.wait_for(ws.receive(), timeout=4)
                    d = json.loads(m.data)
                    kind = d.get("t")
                    types[kind] += 1
                    if kind == "snapshot" and types[kind] <= 3:
                        p = d["data"].get("player", {})
                        samples.append(f"snapshot tick={d['data'].get('tick')} class={p.get('class')} lvl={p.get('level')} hp={p.get('hp')}")
                    elif kind == "screen" and types[kind] <= 3:
                        samples.append(f"screen src={d.get('src')} bytes={len(d.get('data','') or '')}")
                except asyncio.TimeoutError:
                    break
    print("Event counts:", dict(types))
    for s in samples: print(" ", s)

asyncio.run(t())
