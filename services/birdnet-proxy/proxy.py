#!/usr/bin/env python3
import asyncio
import os

LISTEN_HOST = os.getenv("PROXY_LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.getenv("PROXY_LISTEN_PORT", "5432"))
TARGET_HOST = os.environ["BIRDNET_SOURCE_HOST"]
TARGET_PORT = int(os.getenv("BIRDNET_SOURCE_PORT", "5432"))


async def relay(reader, writer):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def handle(client_reader, client_writer):
    peer = client_writer.get_extra_info("peername")
    try:
        upstream_reader, upstream_writer = await asyncio.open_connection(
            TARGET_HOST, TARGET_PORT
        )
        print(f"ALLOW peer={peer} target={TARGET_HOST}:{TARGET_PORT}", flush=True)
        await asyncio.gather(
            relay(client_reader, upstream_writer),
            relay(upstream_reader, client_writer),
        )
    except Exception as exc:
        print(f"ERROR peer={peer} target={TARGET_HOST}:{TARGET_PORT} error={exc}", flush=True)
        try:
            client_writer.close()
            await client_writer.wait_closed()
        except Exception:
            pass


async def main():
    server = await asyncio.start_server(handle, LISTEN_HOST, LISTEN_PORT)
    sockets = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    print(
        f"BirdNET DB proxy listening on {sockets}; "
        f"fixed destination={TARGET_HOST}:{TARGET_PORT}",
        flush=True,
    )
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
