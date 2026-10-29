import math
import time

from ..airlines import airline
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
            text(d, 32, 12, "no aircraft", font("5x7"), DIM, anchor="c")
            return img, 1.0
        cs = a["callsign"] or a.get("r") or a["hex"].upper()
        route = a.get("route") or {}
        name, color = airline(cs)
        name = name or route.get("airline_code") or a.get("r") or ""
        scrolling = False

        # Row 1: airline name in its colour, track arrow on the right
        scrolling |= text_fit(img, 0, 0, 54, name, font("5x7"), color, now, h=7)
        if "track" in a:
            draw_arrow(d, 59.5, 3.5, a["track"])

        # Row 2: route (big) or callsign if the route is unknown
        iata = route.get("_airport_codes_iata", "")
        big = font("6x10")
        legs = iata.split("-") if iata else []
        if len(legs) >= 2:
            x = text(d, 0, 8, legs[0], big, LINE)
            d.line((x + 1, 12, x + 5, 12), fill=SUB)
            d.line((x + 3, 10, x + 5, 12), fill=SUB)
            d.line((x + 3, 14, x + 5, 12), fill=SUB)
            text(d, x + 7, 8, legs[-1], big, LINE)
        else:
            text(d, 0, 8, cs, big, LINE)

        # Row 3: callsign + aircraft type
        small = font("4x6")
        row3 = f"{cs} {a.get('t', '')}".strip() if legs else a.get("t", "")
        scrolling |= text_fit(img, 0, 19, 64, row3, small, SUB, now, h=6)

        # Row 4: altitude, distance, ground speed
        alt = int(a["alt_baro"])
        alt_s = f"FL{alt // 100:03d}" if alt >= 6000 else f"{alt}ft"
        text(d, 0, 26, alt_s, small, DIM)
        text(d, 63, 26, f"{a['dist_km']:.1f}km", small, DIM, anchor="r")
        return img, (0.05 if scrolling else 1.0)
