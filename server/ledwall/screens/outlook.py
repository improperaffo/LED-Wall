"""Hour-by-hour weather widgets at the panel's native 128x64, all with the red rain flag.

timeline: 9-48 h (setting) from the current 3 h slot, icons (with !) over a temperature curve and hourly rain bars
nownext:  big current conditions + the next 5 x 3 h slots with rain probability
rain:     rain-first: headline (when, how much), 24 hourly rain bars, icon strip
"""
import time

from PIL import Image, ImageDraw

from ..icons import draw_icon
from ..render import canvas, font, text
from . import Screen
from .weather import TMAX, TMIN, temp_color

SIZE = (128, 64)
RED = (255, 40, 30)
RAIN = (40, 110, 255)
RAIN_DIM = (12, 30, 80)
LABEL = (150, 150, 150)
DAY = (255, 200, 0)
DIM = (60, 60, 60)
DRY = (120, 220, 120)
CLOCK = (210, 210, 210)
DATE = (0, 170, 255)


def bang(img, x: int, y: int):
    """2x8 red exclamation mark, top-left at (x, y)."""
    d = ImageDraw.Draw(img)
    d.rectangle((x, y, x + 1, y + 4), fill=RED)
    d.rectangle((x, y + 6, x + 1, y + 7), fill=RED)


def icon2x(img, x: int, y: int, code):
    small = Image.new("RGB", (11, 11))
    draw_icon(small, 0, 0, code)
    img.paste(small.resize((22, 22), Image.Resampling.NEAREST), (x, y))


def hour_label(t: float) -> tuple[str, tuple]:
    lt = time.localtime(t)
    return (time.strftime("%a", lt), DAY) if lt.tm_hour == 0 else (f"{lt.tm_hour:02d}", LABEL)


class _Outlook(Screen):
    def __init__(self, weather, settings):
        self.w, self.settings = weather, settings

    def ready(self):
        return self.w.ok

    def wet(self, slot: dict) -> bool:
        r = self.settings.data["rain"]
        return slot["prob"] >= r["prob"] or slot["mm"] >= r["mm"]

    def render(self, now):
        img, d = canvas(SIZE)
        self.draw(img, d, now)
        return img, 60 - (now % 60)


class Timeline(_Outlook):
    """N hours (setting, multiple of 3) from the start of the current 3 h slot: slots across
    the full width (hour, icon, !), temperature curve and hourly rain bars."""
    name = "timeline"
    MIN_SLOT_PX = 13  # an icon (11 px) plus a little air

    def draw(self, img, d, now):
        f4, f5 = font("4x6"), font("5x7")
        n = self.settings.data["options"]["timeline"]["hours"] // 3
        slots = self.w.slots(n, now)
        t0 = slots[0]["t"]
        px = 128 / (n * 3)  # per hour
        top, base = 20, 55  # chart rows; 57-63 are the status line (clock, date, min temp)

        # hourly rain bars (4 mm/h fills the chart, below the max label) and midnight markers
        gap = 1 if px >= 4 else 0
        for i, h in enumerate(self.w.hours_from(t0, n * 3)):
            x0, x1 = round(i * px), round((i + 1) * px) - 1
            if h["mm"] > 0.05:
                bar = max(1, round(min(h["mm"], 4) / 4 * (base - top - 8)))
                d.rectangle((x0 + gap, base - bar + 1, max(x0 + gap, x1 - gap), base), fill=RAIN)
            if time.localtime(h["t"]).tm_hour == 0 and i:
                for y in range(top, base + 1, 2):
                    img.putpixel((x0, y), DIM)

        # icons: one per slot, or per group of slots when a slot is narrower than an icon
        # (the group shows its first slot's icon and is flagged if any of its slots is wet)
        sw = 128 / n
        k = max(1, -(-self.MIN_SLOT_PX // int(sw)))  # ceil
        for g in range(0, n, k):
            group = slots[g:g + k]
            cx = round((g + len(group) / 2) * sw)
            label, color = ("now", LABEL) if g == 0 else hour_label(group[0]["t"])
            text(d, cx, 0, label, f4, color, anchor="c")
            draw_icon(img, cx - 6, 7, group[0]["icon"])
            if any(self.wet(s) for s in group):
                bang(img, cx + 5, 7)

        # temperature: hourly means sit mid-hour; start an hour early so the left edge
        # interpolates between real points instead of running flat
        hours = self.w.hours_from(t0 - 3600, n * 3 + 2)
        c0 = hours[0]["t"] + 1800
        vals = []
        for x in range(128):
            f = (t0 + (x + 0.5) / px * 3600 - c0) / 3600
            i = int(f)
            if i + 1 >= len(hours) or hours[i]["temp"] is None or hours[i + 1]["temp"] is None:
                break
            a, b = hours[i]["temp"], hours[i + 1]["temp"]
            vals.append(a + (b - a) * (f - i))
        if vals:
            lo, hi = min(vals), max(vals)
            if hi - lo < 4:
                lo, hi = (hi + lo) / 2 - 2, (hi + lo) / 2 + 2
            y0, ch = top + 8, base - top - 8  # below the max label
            prev = None
            for x, v in enumerate(vals):
                p = (x, round(y0 + ch - 1 - (v - lo) / (hi - lo) * (ch - 1)))
                if prev:
                    d.line((prev, p), fill=temp_color(v))
                prev = p
            text(d, 127, top + 1, f"{max(vals):.0f}°", f5, TMAX, anchor="r")
            text(d, 127, 57, f"{min(vals):.0f}°", f5, TMIN, anchor="r")

        # status line: clock and date
        lt = time.localtime(now)
        x = 1 + text(d, 1, 57, time.strftime("%H:%M", lt), f5, CLOCK)
        text(d, x + 5, 57, time.strftime("%a %d %b", lt), f5, DATE)


class NowNext(_Outlook):
    name = "nownext"

    def draw(self, img, d, now):
        cur = self.w.data["currentWeather"]
        icon2x(img, 9, 1, cur["icon"])
        t = cur["temperature"]
        text(d, 20, 25, f"{t:.0f}°", font("10x20"), temp_color(t), anchor="c")
        if self.w.days:
            day = self.w.days[0]
            f5 = font("5x7")
            x = 3 + text(d, 3, 50, f"{day['temperatureMin']}", f5, TMIN)
            x += text(d, x, 50, "/", f5, LABEL)
            text(d, x, 50, f"{day['temperatureMax']}", f5, TMAX)
        d.line((40, 2, 40, 61), fill=DIM)
        f4 = font("4x6")
        for i, s in enumerate(self.w.slots(6, now)[1:]):
            cx = 50 + i * 17
            label, color = hour_label(s["t"])
            text(d, cx + 1, 1, label if color == DAY else label + "h", f4, color, anchor="c")
            draw_icon(img, cx - 5, 10, s["icon"])
            if s["temp"] is not None:
                text(d, cx + 1, 25, f"{s['temp']:.0f}°", f4, temp_color(s["temp"]), anchor="c")
            wet = self.wet(s)
            p = s["prob"]
            if p > 0:  # probability (dim) behind amount (bright); 6 mm per 3 h fills it
                d.rectangle((cx - 4, 49 - round(p / 100 * 15), cx + 5, 49), fill=RAIN_DIM)
            if s["mm"] > 0.05:
                d.rectangle((cx - 4, 49 - max(1, round(min(s["mm"], 6) / 6 * 15)), cx + 5, 49), fill=RAIN)
            d.line((cx - 4, 49, cx + 5, 49), fill=DIM if not (p or s["mm"]) else RAIN_DIM)
            if p >= 5 or wet:
                text(d, cx + 1, 52, f"{p:.0f}%", f4, RED if wet else LABEL, anchor="c")
            if wet:
                bang(img, cx + 7, 10)


class RainFirst(_Outlook):
    name = "rain"

    def draw(self, img, d, now):
        f5, f4 = font("5x7"), font("4x6")
        slots = self.w.slots(16, now)  # 48 h
        first = next((s for s in slots if self.wet(s)), None)
        if first is None:
            text(d, 1, 0, "Dry next 48 h", f5, DRY)
        else:  # first wet hour inside the first wet slot, else the slot start
            hrs = self.w.hours_from(first["t"], 3)
            t = next((h["t"] for h in hrs if h["mm"] >= 0.05), first["t"])
            if t <= now:
                when = "now"
            elif t - now < 18 * 3600:
                when = time.strftime("%H:%M", time.localtime(t))
            else:
                when = time.strftime("%a %H:%M", time.localtime(t))
            bang(img, 1, 0)
            text(d, 6, 0, f"Rain {when}", f5, RED)
            total = sum(h["mm"] for h in self.w.hours_from(now, 24))
            if total >= 0.1:
                text(d, 127, 0, f"{total:.1f}mm", f5, RAIN, anchor="r")
        cur = self.w.data["currentWeather"]
        text(d, 127, 9, f"{cur['temperature']:.0f}°", f5, temp_color(cur["temperature"]), anchor="r")
        for i, h in enumerate(self.w.hours_from(now, 24)):  # 24 hourly bars, 4 mm/h = full
            x = 4 + i * 5
            if h["prob"] > 0:
                d.rectangle((x, 40 - round(h["prob"] / 100 * 22), x + 3, 40), fill=RAIN_DIM)
            if h["mm"] > 0.05:
                d.rectangle((x, 40 - max(1, round(min(h["mm"], 4) / 4 * 22)), x + 3, 40), fill=RAIN)
            lt = time.localtime(h["t"])
            if lt.tm_hour % 6 == 0:
                text(d, x + 2, 42, f"{lt.tm_hour:02d}", f4, DAY if lt.tm_hour == 0 else LABEL, anchor="c")
        d.line((4, 41, 123, 41), fill=DIM)
        for i, s in enumerate(slots[:8]):  # icon strip, 8 x 3 h
            draw_icon(img, i * 16 + 2, 51, s["icon"])
            if self.wet(s):
                bang(img, i * 16 + 13, 51)
