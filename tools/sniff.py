import asyncio, aiohttp, sys

async def main():
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect("ws://127.0.0.1:8765/ws") as ws:
            print("connected. waiting up to 8s for messages...")
            try:
                async with asyncio.timeout(8):
                    n = 0
                    async for msg in ws:
                        n += 1
                        text = msg.data[:200] if hasattr(msg, "data") else str(msg)[:200]
                        print(f"[{n}] {text}")
                        if n >= 6: break
            except (asyncio.TimeoutError, TimeoutError):
                pass
            print(f"--- total messages received: {n}")

asyncio.run(main())
