"""Aircraft near a point from adsb.lol, with routes from its VRS standing data."""
import logging
import math
import time
import urllib.error

from ..airlines import aircraft_group
from . import Poller, fetch_json

log = logging.getLogger(__name__)
NM = 1.852
POINT_URL = "https://api.adsb.lol/v2/point/{lat}/{lon}/{nm}"
ROUTE_URL = "https://vrs-standing-data.adsb.lol/routes/{p}/{cs}.json"
ADSBDB_URL = "https://api.adsbdb.com/v0/callsign/{cs}"


def _dist_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def _bearing(lat1, lon1, lat2, lon2) -> float:
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def plausible_leg(airports: list[dict] | None, a: dict) -> tuple[str, str] | None:
    """The (origin, destination) IATA pair of the route leg this aircraft is actually flying.

    The VRS route data is crowd-sourced and callsigns get reused, so a stored route can be
    stale, and multi-stop routes list every stop. A leg A->B is accepted only if the aircraft
    is roughly on the way (A->P->B at most 25 % + 100 km longer than A->B) and its track points
    towards B (within 60 deg, unless it is within 50 km of B and manoeuvring)."""
    airports = airports or []
    lat, lon, track = a.get("lat"), a.get("lon"), a.get("track")
    if len(airports) < 2 or lat is None:
        return None
    best = None
    for A, B in zip(airports, airports[1:]):
        ab = _dist_km(A["lat"], A["lon"], B["lat"], B["lon"])
        ap, pb = _dist_km(A["lat"], A["lon"], lat, lon), _dist_km(lat, lon, B["lat"], B["lon"])
        detour = ap + pb - ab
        if detour > 0.25 * ab + 100:
            continue
        if track is not None and pb > 50:
            off = abs((_bearing(lat, lon, B["lat"], B["lon"]) - track + 180) % 360 - 180)
            if off > 60:
                continue
        if best is None or detour < best[0]:
            best = (detour, (A.get("iata") or A["icao"], B.get("iata") or B["icao"]))
    return best[1] if best else None


class Adsb(Poller):
    name = "flights"

    def __init__(self, lat: float, lon: float, radius_km: float, interval: float = 15):
        super().__init__(interval)
        self.lat, self.lon, self.radius_km = lat, lon, radius_km
        self.groups = {"airliners", "business", "light", "heli"}  # aircraft_group()s to keep
        self.aircraft: list[dict] = []   # nearest first, airborne only
        self.last_seen: tuple[float, dict] | None = None  # (time, aircraft) of the last nearest one
        self.updated = 0.0
        self._routes: dict[str, tuple[float, dict | None]] = {}

    def set_groups(self, groups: set[str]):
        if groups != self.groups:
            self.groups = groups
            self._wake.set()  # re-filter now

    def set_radius(self, km: float):
        if km != self.radius_km:
            self.radius_km = km
            self._wake.set()  # re-query now with the new radius

    def _cached(self, key: str, fetch):
        hit = self._routes.get(key)
        if hit and time.time() - hit[0] < 6 * 3600:
            return hit[1]
        try:
            r = fetch()
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            r = None
        self._routes[key] = (time.time(), r)
        return r

    def route(self, callsign: str) -> dict | None:
        """VRS standing-data route (cached); None if unknown."""
        return self._cached("vrs:" + callsign, lambda: fetch_json(ROUTE_URL.format(p=callsign[:2], cs=callsign)))

    def adsbdb_airports(self, callsign: str) -> list[dict] | None:
        """Route stops from adsbdb.com (cached), in the VRS _airports shape; None if unknown."""
        def fetch():
            resp = fetch_json(ADSBDB_URL.format(cs=callsign)).get("response")
            fr = resp.get("flightroute") if isinstance(resp, dict) else None
            if not fr:
                return None
            stops = [fr.get("origin"), fr.get("midpoint"), fr.get("destination")]
            return [dict(iata=s.get("iata_code"), icao=s.get("icao_code"), lat=s["latitude"], lon=s["longitude"])
                    for s in stops if s]
        return self._cached("adsbdb:" + callsign, fetch)

    def leg(self, a: dict) -> tuple[str, str] | None:
        """First route leg consistent with the aircraft, from VRS, else adsbdb."""
        leg = plausible_leg((a.get("route") or {}).get("_airports"), a)
        if leg is None:
            leg = plausible_leg(self.adsbdb_airports(a["callsign"]), a)
        return leg

    def refresh(self):
        nm = max(1, round(self.radius_km / NM))
        data = fetch_json(POINT_URL.format(lat=self.lat, lon=self.lon, nm=nm))
        out = []
        for a in data.get("ac", []):
            alt = a.get("alt_baro")
            if not isinstance(alt, (int, float)) or "lat" not in a or a.get("seen_pos", 0) > 60:
                continue  # on the ground or no recent position
            a["dist_km"] = a.get("dst", 0) * NM
            if a["dist_km"] > self.radius_km:
                continue
            a["callsign"] = (a.get("flight") or "").strip()
            a["group"] = aircraft_group(a)
            if a["group"] in self.groups:
                out.append(a)
        out.sort(key=lambda a: a["dist_km"])
        for a in out[:3]:
            if a["callsign"]:
                try:
                    a["route"] = self.route(a["callsign"])
                    a["leg"] = self.leg(a)
                except Exception as e:
                    log.debug("route %s: %s", a["callsign"], e)
        self.aircraft = out
        self.updated = time.time()
        if out:
            self.last_seen = (self.updated, out[0])
        log.debug("%d aircraft within %.0f km", len(self.aircraft), self.radius_km)

    @property
    def nearest(self) -> dict | None:
        # stale after a few missed polls (but never sooner than 2 min)
        if self.aircraft and time.time() - self.updated < max(120, 3 * self.interval):
            return self.aircraft[0]
        return None
