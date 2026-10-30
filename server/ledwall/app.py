"""Wiring shared by the server and preview: config, sources, screens, scheduler."""
import time
import tomllib
from pathlib import Path

from .settings import Settings
from .screens.clock import Clock
from .screens.flights import Flights
from .screens.outlook import NowNext, RainFirst, Timeline
from .screens.weather import Forecast, Weather
from .sources.adsb import Adsb
from .sources.flightaware import FlightAware
from .sources.logos import Logos
from .sources.meteoswiss import MeteoSwiss

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.toml"


def load_config(path: Path | None = None) -> dict:
    with open(path or DEFAULT_CONFIG, "rb") as f:
        return tomllib.load(f)


IDLE_POLL_S = 300   # flights nobody is looking at: poll rarely
OFF_POLL_S = 1800   # outside operating hours


class App:
    def __init__(self, cfg: dict, settings: Settings | None = None):
        self.cfg = cfg
        loc, fl = cfg["location"], cfg["flights"]
        self.weather = MeteoSwiss(loc["plz"])
        self.settings = settings or Settings(cfg)
        self.adsb = Adsb(loc["lat"], loc["lon"],
                         self.settings.data["options"]["flights"]["radius_km"], fl["poll_s"],
                         logos=Logos(),
                         flightaware=FlightAware.from_env(int(fl.get("flightaware_daily_cap", 30))))
        self.flights = Flights(self.adsb, fl["alert_km"], fl["alert_max_alt_ft"])
        self.screens = {s.name: s for s in (
            Clock(self.weather), Weather(self.weather), Forecast(self.weather), self.flights,
            Timeline(self.weather, self.settings), NowNext(self.weather, self.settings),
            RainFirst(self.weather, self.settings))}
        self._current = None   # name of the widget on screen
        self._since = 0.0
        self.apply_settings()

    def apply_settings(self):
        """Push poll intervals to the data sources after a settings change."""
        s = self.settings.data
        fo = s["options"]["flights"]
        self.adsb.set_radius(fo["radius_km"])
        self.adsb.set_groups({g for g in ("airliners", "business", "light", "heli") if fo[g]})
        flights_shown = "flights" in self.settings.active()
        self.adsb.flightaware_active = flights_shown and self.settings.is_on()
        if not self.settings.is_on():
            self.weather.set_interval(OFF_POLL_S)
            self.adsb.set_interval(OFF_POLL_S)
            return
        self.weather.set_interval(s["refresh"]["weather"])
        self.adsb.set_interval(s["refresh"]["flights"] if flights_shown else IDLE_POLL_S)

    def show_now(self, name: str):
        self._current, self._since = name, time.time()

    def current(self, now: float):
        """Widget to show now: single mode, or rotate by dwell time, skipping widgets without
        data; a new close aircraft interrupts the rotation if flight alerts are on."""
        s = self.settings.data
        if s["mode"] == "single":
            scr = self.screens[s["single"]]
            # widgets with a meaningful empty state (flights: "No aircraft") stay up; others
            # (weather before its first fetch) fall back to the clock
            self._current = scr.name if scr.ready() or scr.shows_empty else "clock"
            return self.screens[self._current]

        rotation = [(w["name"], w["seconds"]) for w in s["widgets"] if w["enabled"]]
        names = [n for n, _ in rotation]
        if self.flights.pending_alert() and s["flight_alerts"] and "flights" in names:
            self._current, self._since = "flights", now
        if self._current in names:
            i = names.index(self._current)
            if now - self._since < rotation[i][1] and self.screens[self._current].ready():
                return self.screens[self._current]
        else:
            i = -1  # current widget was disabled: start from the top
        for step in range(1, len(names) + 1):
            name = names[(i + step) % len(names)]
            if self.screens[name].ready():
                if name != self._current:
                    self._since = now
                self._current = name
                return self.screens[name]
        self._current = "clock"  # nothing has data yet
        return self.screens["clock"]

    def brightness(self, now: float | None = None) -> int:
        b = self.cfg["brightness"]
        hm = time.strftime("%H:%M", time.localtime(now or time.time()))
        start, end = b["night_start"], b["night_end"]
        night = (start <= hm or hm < end) if start > end else (start <= hm < end)
        return b["night"] if night else b["day"]
