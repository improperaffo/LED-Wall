"""Control page + JSON API, on plain asyncio (no web framework on the Pi).

GET  /                 control page
GET  /api/settings     {"settings": ..., "meta": ...}
PUT  /api/settings     replace (partial ok) -> {"settings": ...} or 400 {"error": ...}
POST /api/show         {"name": "weather"} -> jump to that widget now (rotate mode)
GET  /api/status       what is on the panel, panel connections, data freshness
GET  /api/frame.png    current frame, LED look
"""
import asyncio
import io
import json
import logging
import time
from pathlib import Path

from .render import led_preview
from .settings import Settings

log = logging.getLogger(__name__)
PAGE = Path(__file__).resolve().parent / "web" / "index.html"
MAX_BODY = 64 * 1024
REASONS = {200: "OK", 204: "No Content", 400: "Bad Request", 404: "Not Found",
           405: "Method Not Allowed", 413: "Payload Too Large", 500: "Internal Server Error"}


class Web:
    def __init__(self, app, hub):
        self.app, self.hub = app, hub
        self._png_for: bytes | None = None
        self._png = b""

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            while True:  # keep-alive
                try:
                    line = await asyncio.wait_for(reader.readline(), 30)
                except asyncio.TimeoutError:
                    break
                if not line:
                    break
                method, path, _ = line.decode("latin-1").split(" ", 2)
                headers = {}
                while (h := await reader.readline()) not in (b"\r\n", b"\n", b""):
                    k, _, v = h.decode("latin-1").partition(":")
                    headers[k.strip().lower()] = v.strip()
                length = int(headers.get("content-length", 0))
                if length > MAX_BODY:
                    await self._send(writer, 413, {"error": "body too large"})
                    break
                body = await reader.readexactly(length) if length else b""
                status, payload, ctype = self.route(method, path.split("?")[0], body)
                await self._send(writer, status, payload, ctype)
                if headers.get("connection", "").lower() == "close":
                    break
        except (ConnectionError, asyncio.IncompleteReadError, ValueError):
            pass
        finally:
            writer.close()

    def route(self, method: str, path: str, body: bytes):
        try:
            if path == "/" and method == "GET":
                initial = json.dumps({"settings": self.app.settings.data, "meta": Settings.meta()})
                page = PAGE.read_text().replace("/*INITIAL*/null", initial.replace("</", "<\\/"))
                return 200, page.encode(), "text/html; charset=utf-8"
            if path == "/api/settings":
                if method == "GET":
                    return 200, {"settings": self.app.settings.data, "meta": Settings.meta()}, None
                if method == "PUT":
                    try:
                        data = self.app.settings.update(json.loads(body or b"{}"))
                    except (ValueError, json.JSONDecodeError) as e:
                        return 400, {"error": str(e)}, None
                    self.app.apply_settings()
                    log.info("settings updated: %s", json.dumps(data))
                    return 200, {"settings": data}, None
                return 405, {"error": "use GET or PUT"}, None
            if path == "/api/show" and method == "POST":
                name = json.loads(body or b"{}").get("name")
                if name not in self.app.screens:
                    return 400, {"error": f"unknown widget {name!r}"}, None
                self.app.show_now(name)
                return 204, b"", None
            if path == "/api/status" and method == "GET":
                return 200, self.status(), None
            if path == "/api/frame.png" and method == "GET":
                return 200, self.frame_png(), "image/png"
            return 404, {"error": "not found"}, None
        except Exception:
            log.exception("web %s %s failed", method, path)
            return 500, {"error": "internal error"}, None

    def status(self) -> dict:
        now = time.time()
        age = lambda t: round(now - t) if t else None  # noqa: E731
        return {
            "showing": self.app._current,
            "panels": len(self.hub.clients),
            "brightness": self.hub.brightness,
            "data_age_s": {"weather": age(self.app.weather.updated), "flights": age(self.app.adsb.updated)},
            "aircraft": len(self.app.adsb.aircraft),
        }

    def frame_png(self) -> bytes:
        img = self.hub.image
        if img is None:
            return b""
        raw = img.tobytes()
        if raw != self._png_for:
            buf = io.BytesIO()
            led_preview(img, scale=6).save(buf, "PNG")
            self._png, self._png_for = buf.getvalue(), raw
        return self._png

    @staticmethod
    async def _send(writer, status: int, payload, ctype: str | None = None):
        if isinstance(payload, (dict, list)):
            payload, ctype = json.dumps(payload).encode(), "application/json"
        head = (f"HTTP/1.1 {status} {REASONS.get(status, '')}\r\n"
                f"Content-Type: {ctype or 'application/octet-stream'}\r\n"
                f"Content-Length: {len(payload)}\r\n"
                "Cache-Control: no-store\r\n\r\n")
        writer.write(head.encode() + payload)
        await writer.drain()
