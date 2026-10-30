"""MeteoSwiss precipitation radar (open data): the newest 5-minute RZC rain-rate composite.

STAC collection ch.meteoschweiz.ogd-radar-precip, one item per UTC day ('YYYYMMDD-ch'),
assets 'rzcYYDDDHHMM...h5' (ODIM HDF5, 710 x 640 grid, 1 km, LV95, mm/h). About 4 min latency.
"""
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
        self.rate = None      # numpy (640, 710) float array, mm/h (NaN = no data)
        self.time = 0.0       # epoch of the image (end of its 5-min interval)
        self._asset = None

    def refresh(self):
        import h5py  # optional dependency (Debian/Ubuntu: python3-h5py)
        import io
        now = time.time()
        for day in (time.strftime("%Y%m%d", time.gmtime(now)), time.strftime("%Y%m%d", time.gmtime(now - 86400))):
            try:
                item = fetch_json(ITEM_URL.format(day=day))
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue  # just after midnight UTC the new day's item may not exist yet
                raise
            names = sorted(n for n in item.get("assets", {}) if n.startswith("rzc"))
            if names:
                break
        else:
            raise RuntimeError("no radar images found")
        latest = names[-1]
        if latest == self._asset:
            return
        req = urllib.request.Request(item["assets"][latest]["href"], headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
        with h5py.File(io.BytesIO(raw)) as f:
            what = f["dataset1/what"].attrs
            data = f["dataset1/data1/data"][()]
            g = f["dataset1/data1/what"].attrs
            self.rate = data * g.get("gain", 1.0) + g.get("offset", 0.0)
            end = (what["enddate"].decode() if isinstance(what["enddate"], bytes) else what["enddate"]) + \
                  (what["endtime"].decode() if isinstance(what["endtime"], bytes) else what["endtime"])
        self.time = time.mktime(time.strptime(end, "%Y%m%d%H%M%S")) - time.timezone  # UTC -> epoch
        self._asset = latest
        import numpy as np
        log.info("radar image %s (%s UTC), max %.1f mm/h", latest, end[8:12], float(np.nanmax(self.rate)))

    @property
    def ok(self) -> bool:
        return self.rate is not None and time.time() - self.time < 3600
