"""MeteoSwiss precipitation radar (open data): the newest 5-minute RZC rain-rate composite.

STAC collection ch.meteoschweiz.ogd-radar-precip, one item per UTC day ('YYYYMMDD-ch'),
assets 'rzcYYDDDHHMM...h5' (ODIM HDF5, 710 x 640 grid, 1 km, LV95, mm/h). About 4 min latency.
"""
import calendar
import logging
import time
import urllib.error
import urllib.request

from . import UA, Poller, fetch_json

log = logging.getLogger(__name__)
ITEM_URL = "https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-radar-precip/items/{day}-ch"
# grid: row 0 is the northern edge; cell (r, c) covers x0 + c km .. +1, y_top - r km .. -1
X0, Y_TOP, CELL = 2_255_000, 1_480_000, 1000


class Radar(Poller):
    name = "radar"

    def __init__(self, interval: float = 300):
        super().__init__(interval)
        self.frames: dict[str, tuple[float, object]] = {}  # asset -> (epoch, (640, 710) mm/h array)
        self.keep = 1          # frames to keep: 1 = latest only; set_loop() for animation

    def set_loop(self, minutes: int):
        keep = max(1, minutes // 5 + 1)
        if keep != self.keep:
            self.keep = keep
            self._wake.set()  # fetch the missing history now

    def _names(self) -> list[tuple[str, str]]:
        """(asset name, href) of the newest images, from today's and yesterday's UTC items."""
        out = []
        now = time.time()
        for day in (time.strftime("%Y%m%d", time.gmtime(now - 86400)), time.strftime("%Y%m%d", time.gmtime(now))):
            try:
                item = fetch_json(ITEM_URL.format(day=day))
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue  # just after midnight UTC the new day's item may not exist yet
                raise
            out += [(n, a["href"]) for n, a in item.get("assets", {}).items() if n.startswith("rzc")]
        if not out:
            raise RuntimeError("no radar images found")
        return sorted(out)[-self.keep:]

    @staticmethod
    def _load(href: str):
        import io
        import h5py  # optional dependency (Debian/Ubuntu: python3-h5py)
        req = urllib.request.Request(href, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
        with h5py.File(io.BytesIO(raw)) as f:
            what = f["dataset1/what"].attrs
            g = f["dataset1/data1/what"].attrs
            rate = f["dataset1/data1/data"][()] * g.get("gain", 1.0) + g.get("offset", 0.0)
            txt = lambda v: v.decode() if isinstance(v, bytes) else v  # noqa: E731
            end = txt(what["enddate"]) + txt(what["endtime"])
        return calendar.timegm(time.strptime(end, "%Y%m%d%H%M%S")), rate

    def refresh(self):
        wanted = self._names()
        for name, href in wanted:
            if name not in self.frames:
                self.frames[name] = self._load(href)
                log.info("radar image %s (%s)", name, time.strftime("%H:%M", time.localtime(self.frames[name][0])))
        keep = {n for n, _ in wanted}
        for name in list(self.frames):
            if name not in keep:
                del self.frames[name]

    def sequence(self) -> list[tuple[float, object]]:
        """Frames oldest first, as (epoch, array)."""
        return [self.frames[n] for n in sorted(self.frames)]

    @property
    def time(self) -> float:
        return max((t for t, _ in self.frames.values()), default=0.0)

    @property
    def rate(self):
        seq = self.sequence()
        return seq[-1][1] if seq else None

    @property
    def ok(self) -> bool:
        return bool(self.frames) and time.time() - self.time < 3600
