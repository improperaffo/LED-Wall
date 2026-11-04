"""MeteoSwiss rain radar around home: the latest measured image, then the INCA forecast,
looped over dim lake shores and borders."""
import json
import time
from pathlib import Path

from PIL import Image, ImageDraw

from ..geo import lv95
from ..render import font, text
from . import Screen

SIZE = (128, 64)
BASEMAP = Path(__file__).resolve().parent.parent.parent / "data" / "basemap.json"
# area option -> (centre x, centre y in LV95 m, km per LED)
AREAS = {
    "Lake Geneva": (2_522_000, 1_146_000, 1.0),
    "Romandie": (2_560_000, 1_165_000, 2.0),
    "Switzerland": (2_660_000, 1_190_000, 3.5),
}
LAKE = (0, 70, 60)  # dim teal: must not look like rain
BORDER = (70, 70, 70)
HOME = (255, 255, 255)
NOW_C, MEASURED_C, FORECAST_C = (120, 120, 120), (230, 230, 230), (255, 170, 0)


class Radar(Screen):
    name = "radar"
    FRAME_S, HOLD_S = 0.5, 2.0  # animation: per frame; hold on the measured frame and at the end

    def __init__(self, radar, settings, home: tuple[float, float]):
        self.r, self.settings = radar, settings
        self.home = lv95(home[1], home[0])  # (lat, lon) -> LV95
        self._base = json.loads(BASEMAP.read_text())
        self._drawn: dict[tuple, Image.Image] = {}   # (frame time, kind, area) -> map
        self._t0 = 0.0

    def ready(self):
        return self.r.ok

    def on_show(self, now):
        self._t0 = now

    def loop_seconds(self) -> float:
        n = len(self.r.frames)
        return 2 * self.HOLD_S + max(0, n - 2) * self.FRAME_S if n > 1 else self.HOLD_S

    def _xy(self, area: str, x: float, y: float) -> tuple[float, float]:
        cx, cy, km = AREAS[area]
        return (64 + (x - cx) / (km * 1000), 32 - (y - cy) / (km * 1000))

    def _draw(self, area: str, shapes) -> Image.Image:
        img = Image.new("RGB", SIZE)
        d = ImageDraw.Draw(img)
        for key, col in (("lakes", LAKE), ("borders", BORDER)):
            for line in self._base[key]:
                pts = [self._xy(area, x, y) for x, y in line]
                if any(-5 < px < 133 and -5 < py < 69 for px, py in pts):
                    d.line(pts, fill=col)
        # rain areas, lowest band first: fill the outer ring minus its holes (even-odd)
        for colour, rings in shapes:
            outer = [self._xy(area, x, y) for x, y in rings[0]]
            xs, ys = [p[0] for p in outer], [p[1] for p in outer]
            if max(xs) < 0 or min(xs) > 128 or max(ys) < 0 or min(ys) > 64:
                continue
            mask = Image.new("L", SIZE)
            md = ImageDraw.Draw(mask)
            md.polygon(outer, fill=255)
            for hole in rings[1:]:
                md.polygon([self._xy(area, x, y) for x, y in hole], fill=0)
            img.paste(colour, mask=mask)
        hx, hy = (round(v) for v in self._xy(area, *self.home))  # home: white dot, dark ring
        d.rectangle((hx - 1, hy - 1, hx + 1, hy + 1), fill=(0, 0, 0))
        d.point((hx, hy), fill=HOME)
        return img

    def render(self, now):
        area = self.settings.data["options"]["radar"]["area"]
        frames = self.r.frames
        n = len(frames)
        # loop: measured frame (held), forecast frames, last forecast (held)
        if n > 1:
            pos = (now - self._t0) % self.loop_seconds()
            if pos < self.HOLD_S:
                i, wait = 0, self.HOLD_S - pos
            else:
                k = (pos - self.HOLD_S) / self.FRAME_S
                i = min(1 + int(k), n - 1)
                wait = self.FRAME_S - (pos - self.HOLD_S) % self.FRAME_S if i < n - 1 else self.loop_seconds() - pos
        else:
            i, wait = 0, 30.0
        f = frames[i]
        key = (f["t"], f["kind"], area)
        if key not in self._drawn:
            self._drawn[key] = self._draw(area, f["shapes"])
            live = {(g["t"], g["kind"], area) for g in frames}
            self._drawn = {k: v for k, v in self._drawn.items() if k in live}
        img = self._drawn[key].copy()
        d = ImageDraw.Draw(img)
        f5 = font("5x7")
        # current time top left; time the frame refers to top right (white = measured, amber = forecast)
        nowl = time.strftime("%H:%M", time.localtime(now))
        d.rectangle((0, 0, len(nowl) * 5 + 1, 8), fill=(0, 0, 0))
        text(d, 1, 1, nowl, f5, NOW_C)
        label = time.strftime("%H:%M", time.localtime(f["t"]))
        d.rectangle((127 - len(label) * 5 - 1, 0, 127, 8), fill=(0, 0, 0))
        text(d, 127, 1, label, f5, MEASURED_C if f["kind"] == "measurement" else FORECAST_C, anchor="r")
        if n > 1:  # loop position along the bottom edge
            for k in range(n):
                img.putpixel((round(2 + k * 123 / (n - 1)), 63), MEASURED_C if k == i else (60, 60, 60))
        return img, max(0.05, wait)
