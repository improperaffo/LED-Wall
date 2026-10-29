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

    def _at(self, key: str, i: int):
        a = self.data["graph"][key]
        return a[i] if 0 <= i < len(a) else None

    def hours_from(self, t0: float, n: int) -> list[dict]:
        """n hourly points from the hour containing t0: t, temp, mm (that hour), prob (its 3 h slot)."""
        start = self.data["graph"]["start"] / 1000
        i0 = int((t0 - start) // 3600)
        return [dict(t=start + i * 3600, temp=self._at("temperatureMean1h", i),
                     mm=self._at("precipitation1h", i) or 0.0,
                     prob=self._at("precipitationProbability3h", i // 3) or 0.0)
                for i in range(i0, i0 + n)]

    def slots(self, n: int, now: float | None = None) -> list[dict]:
        """n 3-hour slots from the current one: t, icon, prob (%), mm (3 h total), temp (mid-slot)."""
        start = self.data["graph"]["start"] / 1000
        i0 = int(((now or time.time()) - start) // 10800)
        out = []
        for i in range(i0, i0 + n):
            mm = sum(self._at("precipitation1h", i * 3 + k) or 0.0 for k in range(3))
            out.append(dict(t=start + i * 10800, icon=self._at("weatherIcon3h", i),
                            prob=self._at("precipitationProbability3h", i) or 0.0, mm=mm,
                            temp=self._at("temperatureMean1h", i * 3 + 1)))
        return out

    def is_night(self, ts: float) -> bool:
        g = self.data["graph"]
        for rise, sset in zip(g["sunrise"], g["sunset"]):
            if rise / 1000 <= ts < sset / 1000:
                return False
        return True

    @property
    def days(self) -> list[dict]:
        return self.data["forecast"] if self.data else []
