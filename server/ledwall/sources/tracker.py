"""Track one chosen aircraft anywhere, by flight number (KL591), callsign (KLM591),
registration (PH-EXA) or ICAO hex address (4851ad), via adsb.lol."""
import logging
import re
import time

from ..airlines import VRS_IATA, aircraft_group, airline_iata
from . import Poller, fetch_json
from .adsb import _dist_km, closest_leg

log = logging.getLogger(__name__)
API = "https://api.adsb.lol/v2/{kind}/{value}"
IATA_TO_ICAO: dict[str, list[str]] = {}
for _icao, _iata in VRS_IATA.items():
    IATA_TO_ICAO.setdefault(_iata, []).append(_icao)


def queries(target: str) -> list[tuple[str, str]]:
    """adsb.lol lookups to try for what the user typed, most likely first."""
    t = target.strip().upper().replace(" ", "")
    if not t:
        return []
    if "-" in t:
        return [("reg", t)]
    if re.fullmatch(r"[0-9A-F]{6}", t) and re.search(r"\d", t) and not re.fullmatch(r"[A-Z]{2,3}\d+", t):
        return [("hex", t.lower())]
    out = []
    m = re.fullmatch(r"([A-Z0-9]{2})(\d{1,4}[A-Z]{0,2})", t)
    if m and not re.fullmatch(r"[A-Z]{3}\d.*", t):  # IATA flight number -> ICAO callsign(s)
        out += [("callsign", icao + m.group(2)) for icao in IATA_TO_ICAO.get(m.group(1), [])[:4]]
    out.append(("callsign", t))
    if re.fullmatch(r"[A-Z0-9]{3,6}", t):
        out.append(("reg", t))  # registrations are also written without the dash (HBJXA)
    return out


class Tracker(Poller):
    name = "tracker"

    def __init__(self, adsb, home: tuple[float, float], interval: float = 15):
        super().__init__(interval)
        self.adsb, self.home = adsb, home   # adsb: route/logo helpers; home: (lat, lon)
        self.target = ""
        self.aircraft: dict | None = None
        self.searched: list[str] = []
        self.last_seen: float = 0.0
        self.updated = 0.0

    def set_target(self, target: str):
        if target != self.target:
            self.target, self.aircraft, self.last_seen = target, None, 0.0
            self._wake.set()

    def refresh(self):
        tried = queries(self.target)
        self.searched = list(dict.fromkeys(v for _, v in tried))
        found = None
        for kind, value in tried:
            ac = [a for a in fetch_json(API.format(kind=kind, value=value)).get("ac", []) if "lat" in a]
            if ac:
                found = ac[0]
                break
        self.updated = time.time()
        if not found:
            self.aircraft = None
            return
        a = found
        a["callsign"] = (a.get("flight") or "").strip()
        a["group"] = aircraft_group(a)
        a["home_km"] = _dist_km(self.home[0], self.home[1], a["lat"], a["lon"])
        if a["callsign"]:
            try:
                a["route"] = self.adsb.route(a["callsign"])
                a["leg"] = self.adsb.leg(a)
                stored = (a["route"] or {}).get("_airports") or self.adsb.adsbdb_airports(a["callsign"]) or []
                if not a["leg"]:
                    a["leg_unsure"] = closest_leg(stored, a)
                leg = a["leg"] or a.get("leg_unsure")
                coords = {(ap.get("iata") or ap.get("icao")): ap for ap in stored}
                if leg and leg[0] in coords and leg[1] in coords:
                    o, d = coords[leg[0]], coords[leg[1]]
                    a["total_km"] = _dist_km(o["lat"], o["lon"], d["lat"], d["lon"])
                    a["left_km"] = _dist_km(a["lat"], a["lon"], d["lat"], d["lon"])
                if self.adsb.logos:
                    self.adsb.logos.fetch(airline_iata(a["callsign"]))
            except Exception as e:
                log.debug("tracker route %s: %s", a["callsign"], e)
        if isinstance(a.get("alt_baro"), str):  # "ground"
            a["alt_baro"] = 0
        self.aircraft = a
        self.last_seen = self.updated
