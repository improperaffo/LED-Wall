"""ledwall server: renders 64x32 frames and streams them to the ESP32 over TCP.

Wire protocol (server -> ESP32): b'F' + panel W*H*2 B RGB565 LE | b'B' + 1 B brightness | b'P' ping.
The ESP32 sends b'H' + JSON hello + b'\\n' after connecting.
"""
import argparse
import asyncio
import json
import logging
import socket
import time
import traceback
from pathlib import Path

from .app import App, load_config
from .render import canvas, font, text, to_rgb565

log = logging.getLogger("ledwall")
PING_S = 2.0


class Hub:
    def __init__(self):
        self.clients: set[asyncio.StreamWriter] = set()
        self.frame: bytes | None = None
        self.brightness = 0

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        sock = writer.get_extra_info("socket")
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        log.info("client %s connected", peer)
        self.clients.add(writer)
        try:
            writer.write(b"B" + bytes([self.brightness]))
            if self.frame:
                writer.write(b"F" + self.frame)
            await writer.drain()
            while line := await reader.readline():
                if line.startswith(b"H"):
                    try:
                        log.info("hello from %s: %s", peer, json.loads(line[1:]))
                    except ValueError:
                        log.warning("bad hello from %s: %r", peer, line)
        except (ConnectionError, OSError) as e:
            log.info("client %s error: %s", peer, e)
        finally:
            self.clients.discard(writer)
            writer.close()
            log.info("client %s gone", peer)

    async def send(self, msg: bytes):
        for w in list(self.clients):
            try:
                w.write(msg)
                await asyncio.wait_for(w.drain(), 2)
            except (ConnectionError, OSError, asyncio.TimeoutError) as e:
                log.info("dropping client: %s", e)
                self.clients.discard(w)
                w.close()


def error_frame(msg: str):
    img, d = canvas()
    text(d, 1, 1, "ERROR", font("5x7"), (255, 0, 0))
    text(d, 1, 10, msg[:16], font("4x6"), (200, 200, 200))
    return img


async def render_loop(app: App, hub: Hub):
    panel = (app.cfg["panel"]["width"], app.cfg["panel"]["height"])
    last_sent = 0.0
    while True:
        now = time.time()
        b = app.brightness(now)
        if b != hub.brightness:
            hub.brightness = b
            await hub.send(b"B" + bytes([b]))
        try:
            img, wait = app.current(now).render(now)
        except Exception as e:
            log.error("render failed: %s", traceback.format_exc())
            img, wait = error_frame(type(e).__name__), 5.0
        frame = to_rgb565(img, panel)
        if frame != hub.frame:
            hub.frame = frame
            await hub.send(b"F" + frame)
            last_sent = now
        elif now - last_sent >= PING_S:
            await hub.send(b"P")
            last_sent = now
        await asyncio.sleep(max(0.02, min(wait, PING_S)))


async def main():
    ap = argparse.ArgumentParser(prog="ledwall")
    ap.add_argument("-c", "--config", type=Path)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config(args.config)
    app, hub = App(cfg), Hub()
    server = await asyncio.start_server(hub.handle, cfg["server"]["host"], cfg["server"]["port"])
    log.info("listening on %s", ", ".join(str(s.getsockname()) for s in server.sockets))
    async with server:
        await asyncio.gather(app.weather.run(), app.adsb.run(), render_loop(app, hub))


if __name__ == "__main__":
    asyncio.run(main())
