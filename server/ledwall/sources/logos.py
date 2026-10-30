"""Airline logos as 16x16 LED tiles, fetched once per airline and cached on disk.

Source: the square tail-fin icons on images.kiwi.com, keyed by IATA code. They are the
airlines' trademarks, so they are downloaded at runtime into the cache, never committed.
"""
import io
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageEnhance

from . import UA

log = logging.getLogger(__name__)
URL = "https://images.kiwi.com/airlines/64/{code}.png"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "ledwall" / "logos"
SIZE = 16
RETRY_MISSING_S = 7 * 86400  # re-check airlines without a logo weekly


def to_led(raw: bytes) -> Image.Image:
    """Logo PNG -> 16x16 tile for the panel: white/transparent background off, dark logos
    brightened (navy on white would otherwise vanish), a little extra saturation."""
    im = Image.open(io.BytesIO(raw)).convert("RGBA")
    bg = Image.new("RGBA", im.size, (0, 0, 0, 255))
    bg.alpha_composite(im)
    px = bg.load()
    for y in range(bg.height):
        for x in range(bg.width):
            r, g, b, _ = px[x, y]
            if r > 230 and g > 230 and b > 230:
                px[x, y] = (0, 0, 0, 255)
    tile = bg.convert("RGB").resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    # brighten by the logo's typical (90th percentile) brightness, not its single brightest
    # pixel: a few pale anti-aliasing pixels must not keep a navy logo dark
    lit = sorted(max(p) for p in tile.getdata() if max(p) > 24)
    if lit:
        p90 = lit[int(len(lit) * 0.9) - 1 if len(lit) > 1 else 0]
        if p90 < 200:
            tile = ImageEnhance.Brightness(tile).enhance(min(220 / p90, 6.0))
    return ImageEnhance.Color(tile).enhance(1.3)


class Logos:
    def __init__(self, cache: Path = CACHE):
        self.cache = cache
        self._mem: dict[str, Image.Image | None] = {}

    def _path(self, code: str) -> Path:
        return self.cache / f"{code}.png"

    def _missing(self, code: str) -> Path:
        return self.cache / f"{code}.none"

    def get(self, code: str | None) -> Image.Image | None:
        """Tile for an IATA code if we have it (memory or disk); never touches the network."""
        if not code:
            return None
        if code not in self._mem:
            p = self._path(code)
            self._mem[code] = Image.open(p).convert("RGB") if p.exists() else None
        return self._mem[code]

    def fetch(self, code: str | None):
        """Download and cache the logo if we haven't yet (blocking: call from a worker thread)."""
        if not code or self._path(code).exists():
            return
        miss = self._missing(code)
        if miss.exists() and time.time() - miss.stat().st_mtime < RETRY_MISSING_S:
            return
        self.cache.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL.format(code=code), headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                generic = r.geturl().endswith("/airlines.png")  # unknown code -> placeholder
                raw = r.read()
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            generic, raw = True, b""
        if generic:
            miss.touch()
            log.info("no logo for %s", code)
            return
        to_led(raw).save(self._path(code))
        self._mem.pop(code, None)
        log.info("cached logo for %s", code)
