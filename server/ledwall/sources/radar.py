"""MeteoSwiss rain radar and its INCA forecast, as shown on the MeteoSwiss website and app.

Undocumented but public: www.meteoschweiz.admin.ch/product/output/... (format described in
github.com/chriguschneider/hass-meteoswiss-radar FORMAT.md, MIT). The animation manifest lists
measured RZC frames (5 min, ~12 h back) and INCA forecast frames (5 min for ~6 h, then 10 min,
~30 h ahead). Each frame is rain-intensity areas as chain-code contours on the 1 km Swiss grid.
Source: MeteoSwiss.
"""
import gzip
import json
import logging
import math
import time
import urllib.request

from . import UA, Poller

log = logging.getLogger(__name__)
BASE = "https://www.meteoschweiz.admin.ch"
MAX_FRAMES = 25          # longer horizons are subsampled to keep a loop around 15 s
# legend colours (mm/h bands, lowest first); areas far from all of them are background
LEGEND = ["9a7e95", "0001fc", "058c2d", "05ff05", "feff01", "ffc703", "ff7d01", "ff1900", "af00dd"]


def _get(path: str):
    req = urllib.request.Request(BASE + "/" + path.lstrip("/"),
                                 headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    return json.loads(raw)


def _rgb(hexcol: str) -> tuple[int, int, int]:
    return tuple(int(hexcol[k:k + 2], 16) for k in (0, 2, 4))


def _is_rain(hexcol: str) -> bool:
    c = _rgb(hexcol)
    return min(math.dist(c, _rgb(l)) for l in LEGEND) <= 90


def decode(frame: dict) -> list[tuple[tuple[int, int, int], list[list[tuple[float, float]]]]]:
    """Frame JSON -> [(colour, [outer ring, hole, ...]), ...] in LV95 metres, lowest band first."""
    c = frame["coords"]
    sx = (c["x_max"] - c["x_min"]) / c["x_count"]
    sy = (c["y_max"] - c["y_min"]) / c["y_count"]
    out = []
    for area in frame["areas"]:
        if not _is_rain(area["color"]):
            continue
        colour = _rgb(area["color"])
        for shape in area["shapes"]:
            rings = []
            for ct in shape:
                i, j, d, o = ct["i"], ct["j"], ct["d"], ct["o"]
                ring = []
                for s in range(len(o)):
                    off = int(o[s]) / 10 + 0.05
                    if i % 2 == 0:
                        x, y = c["x_min"] + sx * (i / 2), c["y_min"] + sy * ((j - 1) / 2 + off)
                    else:
                        x, y = c["x_min"] + sx * ((i - 1) / 2 + off), c["y_min"] + sy * (j / 2)
                    ring.append((x * 1000 + 2_000_000, y * 1000 + 1_000_000))  # LV03 km -> LV95 m
                    if 2 * s + 1 < len(d):
                        i += ord(d[2 * s]) - 77
                        j += ord(d[2 * s + 1]) - 77
                if len(ring) >= 3:
                    rings.append(ring)
            if rings:
                out.append((colour, rings))
    return out


class Radar(Poller):
    name = "radar"

    def __init__(self, interval: float = 300):
        super().__init__(interval)
        self.ahead = 2 * 3600       # forecast horizon shown, seconds
        self.frames: list[dict] = []  # [{t, kind: 'measurement'|'forecast', shapes}], in time order
        self._cache: dict[str, list] = {}  # frame url -> decoded shapes (urls are immutable)
        self._version = None
        self.updated = 0.0

    def set_horizon(self, hours: float):
        if hours * 3600 != self.ahead:
            self.ahead = hours * 3600
            self._version = None  # rebuild the frame list now
            self._wake.set()

    def refresh(self):
        version = _get("product/output/versions.json")["precipitation/animation"]
        if version == self._version:
            self.updated = time.time()
            return
        man = _get(f"product/output/precipitation/animation/version__{version}/de/animation.json")
        pics = man["map_images"][0]["pictures"]
        measured = [p for p in pics if p["data_type"] == "measurement"]
        last_t = measured[-1]["timestamp"] if measured else time.time()
        forecast = [p for p in pics if p["data_type"] == "forecast" and p["timestamp"] <= last_t + self.ahead]
        step = max(1, math.ceil(len(forecast) / (MAX_FRAMES - 1)))
        chosen = measured[-1:] + forecast[step - 1::step]
        frames = []
        for p in chosen:
            url = p["radar_url"]
            if url not in self._cache:
                self._cache[url] = decode(_get(url))
            frames.append({"t": p["timestamp"], "kind": p["data_type"], "shapes": self._cache[url]})
        keep = {p["radar_url"] for p in chosen}
        self._cache = {u: s for u, s in self._cache.items() if u in keep}
        self.frames, self._version, self.updated = frames, version, time.time()
        log.info("radar %s: %s + %d forecast frames to %s", version,
                 time.strftime("%H:%M", time.localtime(last_t)), len(frames) - 1,
                 time.strftime("%H:%M", time.localtime(frames[-1]["t"])) if frames else "-")

    @property
    def time(self) -> float:
        """Time of the newest measured image."""
        return max((f["t"] for f in self.frames if f["kind"] == "measurement"), default=0.0)

    @property
    def ok(self) -> bool:
        return bool(self.frames) and time.time() - self.updated < 3600
