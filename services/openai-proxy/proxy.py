#!/usr/bin/env python3
import asyncio
import os

LISTEN_HOST = os.getenv("PROXY_LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.getenv("PROXY_LISTEN_PORT", "8080"))
ALLOWED_HOST = os.getenv("PROXY_ALLOWED_HOST", "api.openai.com")
ALLOWED_PORT = int(os.getenv("PROXY_ALLOWED_PORT", "443"))
MAX_HEADER = 16384


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
        header = await client_reader.readuntil(b"\r\n\r\n")
        if len(header) > MAX_HEADER:
            raise ValueError("header too large")

        first = header.split(b"\r\n", 1)[0].decode("ascii", "strict")
        method, target, _version = first.split(" ", 2)

        if method.upper() != "CONNECT":
            client_writer.write(b"HTTP/1.1 405 Method Not Allowed\r\nConnection: close\r\n\r\n")
            await client_writer.drain()
            return

        host, sep, port_text = target.rpartition(":")
        if not sep:
            raise ValueError("CONNECT target requires host:port")

        try:
            port = int(port_text)
        except ValueError as exc:
            raise ValueError("invalid port") from exc

        if host.lower() != ALLOWED_HOST.lower() or port != ALLOWED_PORT:
            client_writer.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            await client_writer.drain()
            print(f"DENY peer={peer} target={host}:{port}", flush=True)
            return

        upstream_reader, upstream_writer = await asyncio.open_connection(ALLOWED_HOST, ALLOWED_PORT)
        client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await client_writer.drain()
        print(f"ALLOW peer={peer} target={host}:{port}", flush=True)

        await asyncio.gather(
            relay(client_reader, upstream_writer),
            relay(upstream_reader, client_writer),
        )
    except (asyncio.IncompleteReadError, UnicodeError, ValueError) as exc:
        print(f"BAD_REQUEST peer={peer} error={exc}", flush=True)
        try:
            client_writer.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            await client_writer.drain()
        except Exception:
            pass
    except Exception as exc:
        print(f"ERROR peer={peer} error={exc}", flush=True)
        try:
            client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")
            await client_writer.drain()
        except Exception:
            pass
    finally:
        try:
            client_writer.close()
            await client_writer.wait_closed()
        except Exception:
            pass


async def main():
    server = await asyncio.start_server(handle, LISTEN_HOST, LISTEN_PORT)
    sockets = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    print(f"OpenAI allowlist proxy listening on {sockets}; destination={ALLOWED_HOST}:{ALLOWED_PORT}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
