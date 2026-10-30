"""Aircraft near a point from adsb.lol, with routes from its VRS standing data."""
import logging
import time
import urllib.error

from . import Poller, fetch_json

log = logging.getLogger(__name__)
NM = 1.852
POINT_URL = "https://api.adsb.lol/v2/point/{lat}/{lon}/{nm}"
ROUTE_URL = "https://vrs-standing-data.adsb.lol/routes/{p}/{cs}.json"


class Adsb(Poller):
    name = "flights"

    def __init__(self, lat: float, lon: float, radius_km: float, interval: float = 15):
        super().__init__(interval)
        self.lat, self.lon, self.radius_km = lat, lon, radius_km
        self.aircraft: list[dict] = []   # nearest first, airborne only
        self.last_seen: tuple[float, dict] | None = None  # (time, aircraft) of the last nearest one
        self.updated = 0.0
        self._routes: dict[str, tuple[float, dict | None]] = {}

    def set_radius(self, km: float):
        if km != self.radius_km:
            self.radius_km = km
            self._wake.set()  # re-query now with the new radius

    def route(self, callsign: str) -> dict | None:
        """Cached route lookup; None if unknown (non-scheduled callsign)."""
        hit = self._routes.get(callsign)
        if hit and time.time() - hit[0] < 6 * 3600:
            return hit[1]
        try:
            r = fetch_json(ROUTE_URL.format(p=callsign[:2], cs=callsign))
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            r = None
        self._routes[callsign] = (time.time(), r)
        return r

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
            out.append(a)
        out.sort(key=lambda a: a["dist_km"])
        for a in out[:3]:
            if a["callsign"]:
                try:
                    a["route"] = self.route(a["callsign"])
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
