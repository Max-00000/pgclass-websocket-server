import asyncio
import os

from websockets.asyncio.server import serve

port = int(os.environ.get("PORT", 3000))


async def handler(websocket):
    while True:
        message = await websocket.recv()
        print(f"[Received message]: {message}")
        await websocket.send(f"[Echo]: {message}")


async def main():
    async with serve(handler, "0.0.0.0", 443) as server:
        print(f"[Server]: Startup (Serving on port {port})")
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
