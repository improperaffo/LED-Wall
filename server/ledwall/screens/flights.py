import math
import time

from ..airlines import airline_iata, describe, short_type
from ..render import canvas, font, text, text_fit
from . import Screen

SIZE = (128, 64)  # native panel resolution (room for the 16x16 logo)
LINE = (220, 220, 220)
SUB = (0, 190, 255)
DIM = (140, 140, 140)
ARROW = (255, 255, 0)


def draw_arrow(d, cx: float, cy: float, track: float, r: float = 6):
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
        img, d = canvas(SIZE)
        a = self.adsb.nearest
        if a is None:
            self._empty(d, now)
            return img, 5.0
        cs = a["callsign"] or a.get("r") or a["hex"].upper()
        name, color = describe(a)

        # Top: logo (if the airline has one), name in its colour, direction arrow (north = up)
        logo = self.adsb.logos.get(airline_iata(a["callsign"])) if self.adsb.logos else None
        x = 0
        if logo is not None:
            img.paste(logo, (0, 0))
            x = 20
        text_fit(d, x, 3, 112 - x, name, ["6x10", "5x7", "4x6"], color)
        if "track" in a:
            draw_arrow(d, 120.5, 7.5, a["track"])

        # Middle: route (big) if a plausible leg is known, else the callsign
        big = font("9x18B")
        legs = list(a.get("leg") or ())
        if legs:
            x = text(d, 0, 19, legs[0], big, LINE)
            d.line((x + 3, 28, x + 12, 28), fill=SUB, width=2)
            d.polygon([(x + 13, 28), (x + 9, 24), (x + 9, 32)], fill=SUB)
            text(d, x + 17, 19, legs[-1], big, LINE)
        else:
            text_fit(d, 0, 19, 128, cs, ["9x18B", "6x10"], LINE)

        # Below: with a route: callsign + type; without: type + registration (callsigns often
        # differ from the flight numbers Flightradar24 & co show, the registration doesn't)
        t = short_type(a.get("t"))
        ident = a.get("flight_no") or cs  # FlightAware gives the marketed flight number
        row3 = " ".join(filter(None, [ident, t] if legs else [t, a.get("r", "")]))
        text_fit(d, 0, 40, 128, row3, ["6x10", "5x7", "4x6"], SUB)

        # Bottom: altitude, ground speed, distance
        f5 = font("5x7")
        m = int(a["alt_baro"]) * 0.3048  # barometric altitude, feet -> metres
        text(d, 0, 56, f"{round(m, -2):.0f} m" if m >= 1000 else f"{round(m, -1):.0f} m", f5, DIM)
        if a.get("gs") is not None:
            text(d, 64, 56, f"{a['gs'] * 1.852:.0f} km/h", f5, DIM, anchor="c")
        text(d, 127, 56, f"{a['dist_km']:.1f} km", f5, DIM, anchor="r")
        return img, 1.0

    def _empty(self, d, now):
        text(d, 64, 8, "No aircraft", font("9x18B"), LINE, anchor="c")
        text(d, 64, 28, f"within {self.adsb.radius_km:.0f} km", font("6x10"), DIM, anchor="c")
        if self.adsb.last_seen:
            t, last = self.adsb.last_seen
            cs = last["callsign"] or last.get("r") or last["hex"].upper()
            mins = int((now - t) // 60)
            ago = "just now" if mins < 1 else f"{mins} min ago" if mins < 60 else f"{mins // 60} h ago"
            text(d, 64, 48, f"last {cs}, {ago}", font("5x7"), SUB, anchor="c")
