"""Wiring shared by the server and preview: config, sources, screens, scheduler."""
import time
import tomllib
from pathlib import Path

from .screens.clock import Clock
from .screens.flights import Flights
from .screens.weather import Forecast, Weather
from .sources.adsb import Adsb
from .sources.meteoswiss import MeteoSwiss

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.toml"


def load_config(path: Path | None = None) -> dict:
    with open(path or DEFAULT_CONFIG, "rb") as f:
        return tomllib.load(f)


class App:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        loc, fl = cfg["location"], cfg["flights"]
        self.weather = MeteoSwiss(loc["plz"])
        self.adsb = Adsb(loc["lat"], loc["lon"], fl["radius_km"], fl["poll_s"])
        self.flights = Flights(self.adsb, fl["alert_km"], fl["alert_max_alt_ft"])
        self.screens = {s.name: s for s in (
            Clock(self.weather), Weather(self.weather), Forecast(self.weather), self.flights)}
        self.rotation = [(name, float(sec)) for name, sec in cfg["rotation"]["screens"]]
        self._idx = 0
        self._since = 0.0

    def current(self, now: float):
        """Screen to show now: rotate by dwell time, skip screens without data, let flights interrupt."""
        if self.flights.pending_alert():
            names = [n for n, _ in self.rotation]
            if "flights" in names:
                self._idx, self._since = names.index("flights"), now
        name, dwell = self.rotation[self._idx]
        if now - self._since >= dwell or not self.screens[name].ready():
            for step in range(1, len(self.rotation) + 1):
                i = (self._idx + step) % len(self.rotation)
                if self.screens[self.rotation[i][0]].ready():
                    self._idx, self._since = i, now
                    break
            else:
                return self.screens["clock"]
        return self.screens[self.rotation[self._idx][0]]

    def brightness(self, now: float | None = None) -> int:
        b = self.cfg["brightness"]
        hm = time.strftime("%H:%M", time.localtime(now or time.time()))
        start, end = b["night_start"], b["night_end"]
        night = (start <= hm or hm < end) if start > end else (start <= hm < end)
        return b["night"] if night else b["day"]
