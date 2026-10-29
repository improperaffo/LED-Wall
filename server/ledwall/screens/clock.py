import time

from ..render import canvas, font, text
from . import Screen

TIME = (255, 255, 255)
DATE = (0, 170, 255)
TEMP = (255, 140, 0)


class Clock(Screen):
    name = "clock"

    def __init__(self, weather):
        self.weather = weather

    def render(self, now):
        img, d = canvas()
        lt = time.localtime(now)
        big = font("10x20")
        hh, mm = time.strftime("%H", lt), time.strftime("%M", lt)
        # Fixed-width layout so the blinking colon doesn't shift the digits.
        x = (64 - 5 * 10) // 2
        text(d, x, 0, hh, big, TIME)
        if lt.tm_sec % 2 == 0:
            text(d, x + 20, 0, ":", big, TIME)
        text(d, x + 30, 0, mm, big, TIME)
        small = font("5x7")
        text(d, 1, 23, time.strftime("%a %d", lt), small, DATE)
        if self.weather.ok:
            text(d, 63, 23, f"{self.weather.current_temp:.0f}°", small, TEMP, anchor="r")
        return img, 1.0 - (now % 1.0)
