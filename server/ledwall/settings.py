"""User-editable display settings: which widgets, in what order, for how long, how fresh.

Persisted as JSON outside the code tree (deploys must not overwrite it); config.toml only
provides the first-run defaults.
"""
import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

# name -> (label, data source or None)
WIDGETS = {
    "clock": ("Clock", None),
    "weather": ("Weather + 40 h chart", "weather"),
    "forecast": ("3-day forecast", "weather"),
    "flights": ("Flights overhead", "flights"),
}
SOURCES = {
    # name -> (label, min seconds, max seconds); minimums keep us polite to the APIs
    "weather": ("Weather (MeteoSwiss)", 60, 86400),
    "flights": ("Flights (adsb.lol)", 5, 3600),
}
SECONDS_RANGE = (2, 3600)
STATE_PATH = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "ledwall" / "settings.json"


def defaults(cfg: dict) -> dict:
    rotation = [(name, int(sec)) for name, sec in cfg["rotation"]["screens"]]
    listed = {name for name, _ in rotation}
    widgets = [{"name": n, "enabled": True, "seconds": s} for n, s in rotation if n in WIDGETS]
    widgets += [{"name": n, "enabled": False, "seconds": 10} for n in WIDGETS if n not in listed]
    return {
        "mode": "rotate",
        "single": "weather",
        "flight_alerts": True,
        "widgets": widgets,
        "refresh": {"weather": 600, "flights": int(cfg["flights"]["poll_s"])},
    }


def _int(v, lo: int, hi: int, what: str) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise ValueError(f"{what}: not a number")
    if not lo <= n <= hi:
        raise ValueError(f"{what}: must be between {lo} and {hi}")
    return n


def validate(data: dict, base: dict) -> dict:
    """Return a normalized copy of data (missing keys from base). Raises ValueError."""
    if not isinstance(data, dict):
        raise ValueError("settings must be an object")
    out = {}
    out["mode"] = data.get("mode", base["mode"])
    if out["mode"] not in ("rotate", "single"):
        raise ValueError("mode must be 'rotate' or 'single'")
    out["single"] = data.get("single", base["single"])
    if out["single"] not in WIDGETS:
        raise ValueError(f"unknown widget {out['single']!r}")
    out["flight_alerts"] = bool(data.get("flight_alerts", base["flight_alerts"]))

    widgets, seen = [], set()
    for w in data.get("widgets", base["widgets"]):
        name = w.get("name") if isinstance(w, dict) else None
        if name not in WIDGETS or name in seen:
            continue
        seen.add(name)
        widgets.append({
            "name": name,
            "enabled": bool(w.get("enabled", True)),
            "seconds": _int(w.get("seconds", 10), *SECONDS_RANGE, f"{WIDGETS[name][0]} seconds"),
        })
    widgets += [{"name": n, "enabled": False, "seconds": 10} for n in WIDGETS if n not in seen]
    if out["mode"] == "rotate" and not any(w["enabled"] for w in widgets):
        raise ValueError("enable at least one widget to rotate")
    out["widgets"] = widgets

    refresh = {**base["refresh"], **(data.get("refresh") or {})}
    out["refresh"] = {src: _int(refresh.get(src), lo, hi, f"{label} refresh")
                      for src, (label, lo, hi) in SOURCES.items()}
    return out


class Settings:
    def __init__(self, cfg: dict, path: Path = STATE_PATH):
        self.path = path
        self.data = defaults(cfg)
        try:
            self.data = validate(json.loads(path.read_text()), self.data)
            log.info("settings loaded from %s", path)
        except FileNotFoundError:
            log.info("no %s yet, using config.toml defaults", path)
        except (ValueError, json.JSONDecodeError) as e:
            log.warning("ignoring bad %s: %s", path, e)

    def update(self, data: dict) -> dict:
        self.data = validate(data, self.data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2))
        tmp.replace(self.path)
        return self.data

    def active(self) -> list[str]:
        """Widgets that can appear on the panel under the current settings."""
        if self.data["mode"] == "single":
            return [self.data["single"]]
        return [w["name"] for w in self.data["widgets"] if w["enabled"]]

    @staticmethod
    def meta() -> dict:
        return {
            "widgets": [{"name": n, "label": label, "source": src} for n, (label, src) in WIDGETS.items()],
            "sources": [{"name": n, "label": label, "min": lo, "max": hi} for n, (label, lo, hi) in SOURCES.items()],
            "seconds": {"min": SECONDS_RANGE[0], "max": SECONDS_RANGE[1]},
        }
