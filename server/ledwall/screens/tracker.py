"""Follow one chosen flight: airline, route, progress bar with distance left and ETA."""
import time

from ..airlines import airline_iata, describe, short_callsign, short_type
from ..render import canvas, font, text, text_fit
from . import Screen
from .flights import DIM, LINE, SUB, UNSURE, draw_arrow

SIZE = (128, 64)
BAR, DONE, PLANE = (60, 60, 60), (0, 150, 220), (255, 220, 0)


class Tracker(Screen):
    name = "tracker"
    shows_empty = True  # "not in the air" is a useful state

    def __init__(self, tracker):
        self.t = tracker

    def ready(self):
        return bool(self.t.target) and self.t.aircraft is not None

    def render(self, now):
        img, d = canvas(SIZE)
        a = self.t.aircraft
        if a is None:
            self._missing(d, now)
            return img, 5.0
        cs = short_callsign(a["callsign"]) if a["callsign"] else (a.get("r") or a["hex"].upper())
        name, color = describe(a)

        logo = self.t.adsb.logos.get(airline_iata(a["callsign"])) if self.t.adsb.logos else None
        x = 0
        if logo is not None:
            img.paste(logo, (0, 0))
            x = 20
        text_fit(d, x, 3, 112 - x, f"{name} {cs}" if name != cs else cs, ["6x10", "5x7", "4x6"], color)
        if "track" in a:
            draw_arrow(d, 120.5, 7.5, a["track"])

        big = font("9x18B")
        leg = a.get("leg") or a.get("leg_unsure")
        unsure = not a.get("leg") and bool(leg)
        if leg:
            fg, arrow = (UNSURE, UNSURE) if unsure else (LINE, SUB)
            x = text(d, 0, 17, leg[0], big, fg)
            d.line((x + 3, 26, x + 12, 26), fill=arrow, width=2)
            d.polygon([(x + 13, 26), (x + 9, 22), (x + 9, 30)], fill=arrow)
            x += 17 + text(d, x + 17, 17, leg[1], big, fg)
            if unsure:
                text(d, x + 1, 17, "?", big, (255, 170, 0))
        else:
            text_fit(d, 0, 17, 128, " ".join(filter(None, [short_type(a.get("t")), a.get("r")])), ["9x18B", "6x10"], LINE)

        f5 = font("5x7")
        total, left = a.get("total_km"), a.get("left_km")
        if total and left is not None:  # progress bar origin -> destination
            frac = max(0.0, min(1.0, 1 - left / total))
            px = 2 + round(frac * 123)
            d.line((2, 40, 125, 40), fill=BAR, width=3)
            d.line((2, 40, px, 40), fill=DONE, width=3)
            d.rectangle((px - 1, 38, px + 1, 42), fill=PLANE)
            gs = a.get("gs")
            eta = time.strftime("%H:%M", time.localtime(now + left / (gs * 1.852) * 3600)) if gs and gs > 50 else "--:--"
            text(d, 0, 46, f"{left:.0f} km left", f5, DIM)
            text(d, 127, 46, f"ETA {eta}", f5, LINE, anchor="r")
        else:
            text_fit(d, 0, 42, 128, " ".join(filter(None, [cs, short_type(a.get("t")), a.get("r")])),
                     ["6x10", "5x7"], SUB)

        m = int(a.get("alt_baro") or 0) * 0.3048
        text(d, 0, 56, f"{round(m, -2):.0f} m" if m >= 1000 else f"{round(m, -1):.0f} m", f5, DIM)
        if a.get("gs") is not None:
            text(d, 64, 56, f"{a['gs'] * 1.852:.0f} km/h", f5, DIM, anchor="c")
        text(d, 127, 56, f"{a['home_km']:.0f} km", f5, DIM, anchor="r")  # from home
        return img, 2.0

    def _missing(self, d, now):
        if not self.t.target:
            text(d, 64, 18, "No flight chosen", font("6x10"), LINE, anchor="c")
            text_fit(d, 1, 34, 126, "set it on the control page", ["5x7", "4x6"], DIM)
            return
        text(d, 64, 4, self.t.target.upper(), font("9x18B"), LINE, anchor="c")
        text(d, 64, 26, "not in the air", font("6x10"), DIM, anchor="c")
        if self.t.last_seen:
            mins = int((now - self.t.last_seen) // 60)
            text(d, 64, 40, f"last seen {mins} min ago" if mins < 120 else f"last seen {mins // 60} h ago",
                 font("5x7"), SUB, anchor="c")
        if self.t.searched:
            text_fit(d, 0, 54, 128, "searched " + ", ".join(self.t.searched[:3]), ["4x6", "tom-thumb"], DIM)
