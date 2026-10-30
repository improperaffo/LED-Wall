import math
import time

from ..airlines import describe, short_type
from ..render import canvas, font, text, text_fit
from . import Screen

LINE = (220, 220, 220)
SUB = (0, 190, 255)
DIM = (140, 140, 140)
ARROW = (255, 255, 0)


def draw_arrow(d, cx: float, cy: float, track: float, r: float = 3.5):
    """Small plane-ish arrow pointing along the track (degrees, 0 = north/up)."""
    a = math.radians(track)
    def pt(dist, ang):
        return (cx + dist * math.sin(a + ang), cy - dist * math.cos(a + ang))
    d.polygon([pt(r, 0), pt(r, math.radians(140)), pt(r * 0.3, math.pi), pt(r, math.radians(-140))], fill=ARROW)


class Flights(Screen):
    """FlightWall style: the nearest airborne aircraft."""
    name = "flights"
    shows_empty = True

    def __init__(self, adsb, alert_km: float, alert_max_alt_ft: float):
        self.adsb = adsb
        self.alert_km = alert_km
        self.alert_max_alt = alert_max_alt_ft
        self._alerted: dict[str, float] = {}   # hex -> time we interrupted for it
        self._shown_since = 0.0

    def ready(self):
        return self.adsb.nearest is not None

    def pending_alert(self) -> bool:
        """True once per aircraft that comes close and low enough to interrupt the rotation."""
        a = self.adsb.nearest
        now = time.time()
        self._alerted = {k: v for k, v in self._alerted.items() if now - v < 1800}
        if a and a["dist_km"] <= self.alert_km and a["alt_baro"] <= self.alert_max_alt and a["hex"] not in self._alerted:
            self._alerted[a["hex"]] = now
            return True
        return False

    def render(self, now):
        img, d = canvas()
        a = self.adsb.nearest
        if a is None:
            f4 = font("4x6")
            text(d, 32, 2, "No aircraft", font("5x7"), LINE, anchor="c")
            text(d, 32, 11, f"within {self.adsb.radius_km:.0f} km", f4, DIM, anchor="c")
            if self.adsb.last_seen:
                t, last = self.adsb.last_seen
                cs = last["callsign"] or last.get("r") or last["hex"].upper()
                mins = int((now - t) // 60)
                ago = "just now" if mins < 1 else f"{mins} min ago" if mins < 60 else f"{mins // 60} h ago"
                text(d, 32, 19, f"last {cs}", f4, SUB, anchor="c")
                text(d, 32, 26, ago, f4, DIM, anchor="c")
            return img, 5.0
        cs = a["callsign"] or a.get("r") or a["hex"].upper()
        name, color = describe(a)

        # Row 1: airline name in its colour, track arrow on the right
        text_fit(d, 0, 0, 54, name, ["5x7", "4x6", "tom-thumb"], color)
        if "track" in a:
            draw_arrow(d, 59.5, 3.5, a["track"])

        # Row 2: route (big) if a plausible leg is known, else the callsign
        big = font("6x10")
        legs = list(a.get("leg") or ())
        if legs:
            x = text(d, 0, 8, legs[0], big, LINE)
            d.line((x + 1, 12, x + 5, 12), fill=SUB)
            d.line((x + 3, 10, x + 5, 12), fill=SUB)
            d.line((x + 3, 14, x + 5, 12), fill=SUB)
            text(d, x + 7, 8, legs[-1], big, LINE)
        else:
            text(d, 0, 8, cs, big, LINE)

        # Row 3: with a route: callsign + type; without: type + registration (callsigns often
        # differ from the flight numbers Flightradar24 & co show, the registration doesn't)
        small = font("4x6")
        t = short_type(a.get("t"))
        row3 = " ".join(filter(None, [cs, t] if legs else [t, a.get("r", "")]))
        text_fit(d, 0, 19, 64, row3, ["4x6", "tom-thumb"], SUB)

        # Row 4: altitude, distance, ground speed
        alt = int(a["alt_baro"])
        m = alt * 0.3048  # barometric altitude, feet -> metres (100 m steps up high, 10 m low)
        alt_s = f"{round(m, -2):.0f}m" if m >= 1000 else f"{round(m, -1):.0f}m"
        text(d, 0, 26, alt_s, small, DIM)
        text(d, 63, 26, f"{a['dist_km']:.1f}km", small, DIM, anchor="r")
        return img, 1.0
