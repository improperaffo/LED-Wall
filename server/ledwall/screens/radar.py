"""MeteoSwiss rain radar around home: latest 5-minute rain rate over lake shores and borders."""
import json
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
        self._frames: dict[tuple, Image.Image] = {}   # (image time, area) -> drawn map

    def ready(self):
        return self.r.ok

    def _xy(self, area: str, x: float, y: float) -> tuple[float, float]:
        cx, cy, km = AREAS[area]
        return (64 + (x - cx) / (km * 1000), 32 - (y - cy) / (km * 1000))

    @staticmethod
    def _edges(raw, limit: int):
        """LED edges in grid cells: integers, strictly increasing, inside the grid."""
        import numpy as np
        e = np.clip(raw.astype(int), 0, limit)
        for k in range(1, len(e)):
            if e[k] <= e[k - 1]:
                e[k] = e[k - 1] + 1
        return np.minimum(e, limit)

    def _draw(self, area: str, rate) -> Image.Image:
        import numpy as np
        img = Image.new("RGB", SIZE)
        d = ImageDraw.Draw(img)
        for key, col in (("lakes", LAKE), ("borders", BORDER)):
            for line in self._base[key]:
                pts = [self._xy(area, x, y) for x, y in line]
                if any(-5 < px < 133 and -5 < py < 69 for px, py in pts):
                    d.line(pts, fill=col)
        # rain: each LED takes the heaviest radar cell it covers, so small showers survive
        # zooming out (vectorised: block maxima with reduceat over the LED edges in grid cells)
        cx, cy, km = AREAS[area]
        step = km * 1000
        rows = self._edges(np.floor((Y_TOP - (cy + (32 - np.arange(65)) * step)) / CELL), rate.shape[0])
        cols = self._edges(np.floor((cx + (np.arange(129) - 64) * step - X0) / CELL), rate.shape[1])
        block = np.nan_to_num(rate[rows[0]:rows[-1], cols[0]:cols[-1]], nan=-1.0)
        m = np.maximum.reduceat(block, rows[:-1] - rows[0], axis=0)
        m = np.maximum.reduceat(m, cols[:-1] - cols[0], axis=1)
        level = np.digitize(m, [t for t, _ in SCALE])  # 0 = below 0.1 mm/h
        palette = np.array([(0, 0, 0)] + [c for _, c in SCALE], dtype=np.uint8)
        pixels = np.array(img)
        wet = level > 0
        pixels[wet] = palette[level[wet]]
        img = Image.fromarray(pixels)
        d = ImageDraw.Draw(img)
        hx, hy = self._xy(area, *self.home)  # home: white dot with a dark ring
        hx, hy = round(hx), round(hy)
        d.rectangle((hx - 1, hy - 1, hx + 1, hy + 1), fill=(0, 0, 0))
        d.point((hx, hy), fill=HOME)
        return img

    FRAME_S, HOLD_S = 0.5, 2.0  # animation: per frame, and on the newest frame

    def on_show(self, now):
        self._t0 = now

    def loop_seconds(self) -> float:
        n = len(self.r.frames)
        return (n - 1) * self.FRAME_S + self.HOLD_S if n > 1 else self.HOLD_S

    def _frame(self, t: float, rate, area: str) -> Image.Image:
        key = (t, area)
        if key not in self._frames:
            self._frames[key] = self._draw(area, rate)
            live = {(ft, area) for ft, _ in self.r.sequence()}
            for k in list(self._frames):  # forget frames that left the loop
                if k not in live:
                    del self._frames[k]
        return self._frames[key]

    def render(self, now):
        area = self.settings.data["options"]["radar"]["area"]
        seq = self.r.sequence()
        n = len(seq)
        if n > 1:  # loop: oldest -> newest, then hold the newest
            pos = (now - getattr(self, "_t0", 0.0)) % self.loop_seconds()
            i = min(int(pos / self.FRAME_S), n - 1)
            wait = self.FRAME_S - pos % self.FRAME_S if i < n - 1 else self.loop_seconds() - pos
        else:
            i, wait = n - 1, 30.0
        t, rate = seq[i]
        img = self._frame(t, rate, area).copy()
        d = ImageDraw.Draw(img)
        f = font("5x7")
        # current time top left; image time top right (white on the newest frame, amber
        # while showing the past)
        nowl = time.strftime("%H:%M", time.localtime(now))
        d.rectangle((0, 0, len(nowl) * 5 + 1, 8), fill=(0, 0, 0))
        text(d, 1, 1, nowl, f, (120, 120, 120))
        label = time.strftime("%H:%M", time.localtime(t))
        d.rectangle((127 - len(label) * 5 - 1, 0, 127, 8), fill=(0, 0, 0))
        text(d, 127, 1, label, f, (230, 230, 230) if i == n - 1 else (255, 170, 0), anchor="r")
        if n > 1:  # loop position: one dot per frame along the bottom edge
            for k in range(n):
                x = round(2 + k * 123 / (n - 1))
                img.putpixel((x, 63), (230, 230, 230) if k == i else (60, 60, 60))
        return img, max(0.05, wait)
