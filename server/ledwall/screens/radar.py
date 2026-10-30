"""MeteoSwiss rain radar around home: latest 5-minute rain rate over lake shores and borders."""
import json
import math
import time
from pathlib import Path

from PIL import Image, ImageDraw

from ..geo import lv95
from ..render import font, text
from ..sources.radar import CELL, X0, Y_TOP
from . import Screen

SIZE = (128, 64)
BASEMAP = Path(__file__).resolve().parent.parent.parent / "data" / "basemap.json"
# area option -> (centre x, centre y in LV95 m, km per LED)
AREAS = {
    "Lake Geneva": (2_522_000, 1_146_000, 1.0),
    "Romandie": (2_560_000, 1_165_000, 2.0),
    "Switzerland": (2_660_000, 1_190_000, 3.5),
}
# mm/h thresholds -> colour (MeteoSwiss-like: blues, green, yellow, orange, red, magenta)
SCALE = [(0.1, (40, 80, 200)), (0.5, (40, 130, 255)), (1, (0, 170, 210)), (2, (0, 190, 70)),
         (4, (210, 210, 0)), (10, (255, 130, 0)), (20, (255, 30, 0)), (50, (220, 0, 220)),
         (100, (255, 255, 255))]
LAKE = (0, 70, 60)  # dim teal: must not look like light rain
BORDER = (70, 70, 70)
HOME = (255, 255, 255)


def colour(mm: float):
    c = None
    for limit, col in SCALE:
        if mm >= limit:
            c = col
    return c


class Radar(Screen):
    name = "radar"

    def __init__(self, radar, settings, home: tuple[float, float]):
        self.r, self.settings = radar, settings
        self.home = lv95(home[1], home[0])  # (lat, lon) -> LV95
        self._base = json.loads(BASEMAP.read_text())
        self._cache: tuple | None = None   # (key, image)

    def ready(self):
        return self.r.ok

    def _xy(self, area: str, x: float, y: float) -> tuple[float, float]:
        cx, cy, km = AREAS[area]
        return (64 + (x - cx) / (km * 1000), 32 - (y - cy) / (km * 1000))

    def _draw(self, area: str) -> Image.Image:
        import numpy as np
        img = Image.new("RGB", SIZE)
        d = ImageDraw.Draw(img)
        for key, col in (("lakes", LAKE), ("borders", BORDER)):
            for line in self._base[key]:
                pts = [self._xy(area, x, y) for x, y in line]
                if any(-5 < px < 133 and -5 < py < 69 for px, py in pts):
                    d.line(pts, fill=col)
        # rain: each LED takes the heaviest radar cell it covers, so small showers survive zooming out
        cx, cy, km = AREAS[area]
        rate, px = self.r.rate, img.load()
        rows, cols = rate.shape
        for j in range(64):
            y_top = cy + (32 - j) * km * 1000
            r0 = int((Y_TOP - y_top) // CELL)
            r1 = max(r0 + 1, int(math.ceil((Y_TOP - (y_top - km * 1000)) / CELL)))
            if r1 <= 0 or r0 >= rows:
                continue
            for i in range(128):
                x_left = cx + (i - 64) * km * 1000
                c0 = int((x_left - X0) // CELL)
                c1 = max(c0 + 1, int(math.ceil((x_left + km * 1000 - X0) / CELL)))
                if c1 <= 0 or c0 >= cols:
                    continue
                block = rate[max(r0, 0):r1, max(c0, 0):c1]
                if block.size and not np.all(np.isnan(block)):
                    c = colour(float(np.nanmax(block)))
                    if c:
                        px[i, j] = c
        hx, hy = self._xy(area, *self.home)  # home: white dot with a dark ring
        hx, hy = round(hx), round(hy)
        d.rectangle((hx - 1, hy - 1, hx + 1, hy + 1), fill=(0, 0, 0))
        d.point((hx, hy), fill=HOME)
        return img

    def render(self, now):
        area = self.settings.data["options"]["radar"]["area"]
        key = (self.r.time, area)
        if not self._cache or self._cache[0] != key:
            self._cache = (key, self._draw(area))
        img = self._cache[1].copy()
        d = ImageDraw.Draw(img)
        label = time.strftime("%H:%M", time.localtime(self.r.time))
        f = font("5x7")
        d.rectangle((0, 0, len(label) * 5 + 1, 8), fill=(0, 0, 0))
        text(d, 1, 1, label, f, (200, 200, 200))
        return img, 30.0
