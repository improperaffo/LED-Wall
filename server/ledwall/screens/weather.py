import time

from PIL import ImageDraw

from ..icons import draw_icon
from ..render import canvas, font, text
from . import Screen

TEMP = (255, 140, 0)
TMIN = (80, 160, 255)
TMAX = (255, 80, 60)
RAIN = (30, 90, 255)
NIGHT_BG = (0, 0, 22)
MIDNIGHT = (70, 70, 70)
LABEL = (150, 150, 150)
GRID = (30, 30, 30)

CHART_X, CHART_W = 24, 40   # one column per hour
TOP, BOTTOM = 7, 31         # temperature line area
RAIN_MAX_MM = 4.0           # mm/h that fills the chart height


def temp_color(t: float) -> tuple[int, int, int]:
    if t <= 0:
        return (120, 180, 255)
    if t < 10:
        return (80, 220, 200)
    if t < 20:
        return (255, 200, 0)
    if t < 28:
        return (255, 130, 0)
    return (255, 50, 30)


class Weather(Screen):
    """Now: icon + temperature + today min/max; right: next 40 h temperature and rain."""
    name = "weather"

    def __init__(self, weather):
        self.w = weather

    def ready(self):
        return self.w.ok

    def render(self, now):
        img, d = canvas()
        w = self.w
        draw_icon(img, 6, 0, w.current_icon)
        t = w.current_temp
        text(d, 12, 12, f"{t:.0f}°", font("6x10"), temp_color(t), anchor="c")
        if w.days:
            day = w.days[0]
            f = font("4x6")
            x = text(d, 0, 25, f"{day['temperatureMin']}", f, TMIN)
            x += text(d, x, 25, "/", f, LABEL)
            text(d, x, 25, f"{day['temperatureMax']}", f, TMAX)
        self._chart(img, d, now)
        return img, 60 - (now % 60)

    def _chart(self, img, d: ImageDraw.ImageDraw, now):
        hours = self.w.hourly(CHART_W, now)
        if len(hours) < 2:
            return
        temps = [h[1] for h in hours]
        lo, hi = min(temps), max(temps)
        if hi - lo < 4:  # don't amplify noise on flat days
            mid = (hi + lo) / 2
            lo, hi = mid - 2, mid + 2
        span = BOTTOM - TOP

        def ty(v):
            return round(BOTTOM - (v - lo) / (hi - lo) * span)

        for i, (ts, _, mm) in enumerate(hours):
            x = CHART_X + i
            if self.w.is_night(ts + 1800):
                d.line((x, TOP, x, BOTTOM), fill=NIGHT_BG)
            if time.localtime(ts).tm_hour == 0:
                for y in range(TOP, BOTTOM + 1, 2):
                    img.putpixel((x, y), MIDNIGHT)
            if mm > 0.05:
                bar = max(1, round(min(mm, RAIN_MAX_MM) / RAIN_MAX_MM * span))
                d.line((x, BOTTOM, x, BOTTOM - bar + 1), fill=RAIN)
        prev = None
        for i, (_, v, _) in enumerate(hours):
            p = (CHART_X + i, ty(v))
            if prev:
                d.line((prev, p), fill=temp_color(v))
            prev = p
        f = font("4x6")
        text(d, CHART_X, 0, f"{max(temps):.0f}°", f, TMAX)
        text(d, 63, 0, f"{min(temps):.0f}°", f, TMIN, anchor="r")
        total = sum(h[2] for h in hours)
        if total >= 0.1:
            text(d, CHART_X + 20, 0, f"{total:.0f}mm" if total >= 1 else f".{total*10:.0f}mm", f, RAIN, anchor="c")


class Forecast(Screen):
    """Three days: weekday, icon, min/max, rain."""
    name = "forecast"

    def __init__(self, weather):
        self.w = weather

    def ready(self):
        return self.w.ok and len(self.w.days) >= 3

    def render(self, now):
        img, d = canvas()
        f = font("4x6")
        for i, day in enumerate(self.w.days[:3]):
            cx = 10 + i * 22
            name = "Today" if i == 0 else time.strftime("%a", time.strptime(day["dayDate"], "%Y-%m-%d"))
            text(d, cx + 1, 0, name, f, LABEL, anchor="c")
            draw_icon(img, cx - 5, 7, day["iconDay"])
            lo, hi = f"{day['temperatureMin']}", f"{day['temperatureMax']}"
            wlo = len(lo) * 4
            x = cx + 1 - (wlo + 4 + len(hi) * 4) // 2
            x += text(d, x, 19, lo, f, TMIN)
            x += text(d, x, 19, "/", f, LABEL)
            text(d, x, 19, hi, f, TMAX)
            mm = day.get("precipitation", 0)
            if mm >= 0.1:
                text(d, cx + 1, 26, f"{mm:.0f}mm" if mm >= 1 else f".{mm*10:.0f}mm", f, RAIN, anchor="c")
        return img, 60 - (now % 60)
