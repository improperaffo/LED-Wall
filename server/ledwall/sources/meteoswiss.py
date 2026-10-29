"""MeteoSwiss app API (the one behind the MeteoSwiss phone app), per postcode."""
import logging
import time

from . import Poller, fetch_json

log = logging.getLogger(__name__)
URL = "https://app-prod-ws.meteoswiss-app.ch/v1/plzDetail?plz={plz}00"


class MeteoSwiss(Poller):
    name = "weather"

    def __init__(self, plz: int, interval: float = 600):
        super().__init__(interval)
        self.url = URL.format(plz=plz)
        self.data: dict | None = None
        self.updated = 0.0

    def refresh(self):
        self.data = fetch_json(self.url)
        self.updated = time.time()
        log.info("weather updated: %s°C", self.current_temp)

    @property
    def ok(self) -> bool:
        return self.data is not None and time.time() - self.updated < 6 * 3600

    @property
    def current_temp(self) -> float | None:
        return self.data["currentWeather"]["temperature"] if self.data else None

    @property
    def current_icon(self) -> int | None:
        return self.data["currentWeather"]["icon"] if self.data else None

    def hourly(self, hours: int, now: float | None = None) -> list[tuple[float, float, float]]:
        """(epoch, temp °C, precip mm/h) for the next `hours`, starting at the current hour."""
        g = self.data["graph"]
        start = g["start"] / 1000
        now = now or time.time()
        i0 = max(0, int((now - start) // 3600))
        temps = g["temperatureMean1h"][i0:i0 + hours]
        rain = g["precipitation1h"][i0:i0 + hours]
        return [(start + (i0 + k) * 3600, t, r) for k, (t, r) in enumerate(zip(temps, rain))]

    def is_night(self, ts: float) -> bool:
        g = self.data["graph"]
        for rise, sset in zip(g["sunrise"], g["sunset"]):
            if rise / 1000 <= ts < sset / 1000:
                return False
        return True

    @property
    def days(self) -> list[dict]:
        return self.data["forecast"] if self.data else []
