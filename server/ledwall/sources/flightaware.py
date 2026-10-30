"""Optional paid route source: FlightAware AeroAPI, for callsigns the free databases miss.

Enabled only if LEDWALL_FLIGHTAWARE_KEY is set (systemd EnvironmentFile, never the repo).
Cost control: the caller asks only for the aircraft on screen; answers (also 'not found')
are cached 6 h per callsign; at most `daily_cap` requests per day, counted on disk.
"""
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import UA

log = logging.getLogger(__name__)
URL = "https://aeroapi.flightaware.com/aeroapi/flights/{ident}?ident_type=designator"
STATE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "ledwall" / "flightaware.json"


class FlightAware:
    def __init__(self, key: str, daily_cap: int = 30, state: Path = STATE):
        self.key, self.daily_cap, self.state = key, daily_cap, state
        self._cache: dict[str, tuple[float, dict | None]] = {}
        try:
            self._count = json.loads(state.read_text())
        except (OSError, ValueError):
            self._count = {}

    @classmethod
    def from_env(cls, daily_cap: int):
        key = os.environ.get("LEDWALL_FLIGHTAWARE_KEY", "").strip()
        return cls(key, daily_cap) if key else None

    @property
    def used_today(self) -> int:
        return self._count.get(time.strftime("%Y-%m-%d"), 0)

    def _spend(self):
        day = time.strftime("%Y-%m-%d")
        self._count = {day: self.used_today + 1}  # keep today only
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text(json.dumps(self._count))

    def lookup(self, callsign: str) -> dict | None:
        """The flight with this callsign that is airborne now: {'leg': (orig, dest), 'number': 'TO3851'}."""
        hit = self._cache.get(callsign)
        if hit and time.time() - hit[0] < 6 * 3600:
            return hit[1]
        if self.used_today >= self.daily_cap:
            return None  # over budget: don't cache, retry tomorrow
        req = urllib.request.Request(URL.format(ident=urllib.parse.quote(callsign)),
                                     headers={"x-apikey": self.key, "Accept": "application/json", "User-Agent": UA})
        self._spend()
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                flights = json.load(r).get("flights") or []
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                flights = []
            else:
                log.warning("FlightAware %s: HTTP %s", callsign, e.code)
                return None
        result = None
        for f in flights:  # newest first; the airborne one has taken off but not landed
            if f.get("actual_off") and not f.get("actual_on"):
                code = lambda ap: (ap or {}).get("code_iata") or (ap or {}).get("code_icao")  # noqa: E731
                o, d = code(f.get("origin")), code(f.get("destination"))
                if o and d:
                    result = {"leg": (o, d), "number": f.get("ident_iata") or f.get("ident")}
                break
        log.info("FlightAware %s -> %s (%d/%d today)", callsign, result, self.used_today, self.daily_cap)
        self._cache[callsign] = (time.time(), result)
        return result
