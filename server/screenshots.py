#!/usr/bin/env python3
"""Regenerate the README screenshots (docs/screenshots/*.png) with the LED look.

Weather widgets use live MeteoSwiss data with a simulated afternoon shower (so the rain cues
show); flights use example aircraft and no airline logos (trademarks stay out of the repo).
Usage: python3 server/screenshots.py
"""
import copy
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ledwall.app import App, load_config  # noqa: E402
from ledwall.render import led_preview  # noqa: E402
from ledwall.settings import Settings  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"


def with_shower(data: dict, now: float) -> dict:
    """Copy of the MeteoSwiss data with rain 4-12 h from now."""
    d = copy.deepcopy(data)
    g = d["graph"]
    i0 = int((now - g["start"] / 1000) // 3600)
    for k, mm in zip(range(i0 + 4, i0 + 13), [0.1, 0.4, 1.2, 2.5, 3.1, 1.8, 0.9, 0.3, 0.1]):
        g["precipitation1h"][k] = mm
    for k, p in zip(range((i0 + 3) // 3, (i0 + 3) // 3 + 4), [40, 80, 70, 30]):
        g["precipitationProbability3h"][k] = p
        g["weatherIcon3h"][k] = 20 if p >= 70 else 6
    return d


FLIGHTS = {
    "flights": {"hex": "4b1805", "callsign": "EZS1435", "t": "A21N", "r": "HB-JXA", "alt_baro": 7400,
                "track": 130.0, "gs": 260, "dist_km": 3.2, "lat": 46.30, "lon": 6.25, "group": "airliners",
                "leg": ("GVA", "SUF")},
    "flights-unsure": {"hex": "4ca9a1", "callsign": "RYR8YM", "t": "B738", "r": "EI-EKH", "alt_baro": 36200,
                       "track": 317.8, "gs": 440, "dist_km": 9.7, "lat": 46.58, "lon": 6.66,
                       "group": "airliners", "leg_unsure": ("MXP", "MAD")},
    "flights-heli": {"hex": "4b3306", "callsign": "RGAIK", "t": "EC45", "r": "HB-TIK", "category": "A7",
                     "alt_baro": 2460, "track": 60.0, "gs": 113, "dist_km": 5.6, "lat": 46.5, "lon": 6.6,
                     "group": "heli"},
}


TRACKED = {"hex": "440f3c", "callsign": "EJU82VC", "t": "A320", "r": "OE-IVD", "alt_baro": 36000, "track": 312.0,
           "gs": 472, "lat": 46.7, "lon": 6.3, "group": "airliners", "leg": ("JMK", "ORY"),
           "total_km": 2236, "left_km": 377, "home_km": 21}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    with tempfile.TemporaryDirectory() as tmp:
        app = App(cfg, Settings(cfg, Path(tmp) / "settings.json"))
        app.adsb.logos = None
        now = time.time()
        app.weather.refresh()
        real = app.weather.data
        for name in ("clock", "timeline"):  # the widgets shown in the README
            app.weather.data = with_shower(real, now) if name == "timeline" else real
            img, _ = app.screens[name].render(now)
            led_preview(img.resize((128, 64)) if img.size != (128, 64) else img, scale=5).save(OUT / f"{name}.png")
            print(OUT / f"{name}.png")
        for name, ac in FLIGHTS.items():
            app.adsb.aircraft, app.adsb.updated = [ac], now
            led_preview(app.screens["flights"].render(now)[0], scale=5).save(OUT / f"{name}.png")
            print(OUT / f"{name}.png")
        app.tracker.target, app.tracker.aircraft = "EC82VC", TRACKED
        led_preview(app.screens["tracker"].render(now)[0], scale=5).save(OUT / "tracker.png")
        print(OUT / "tracker.png")


if __name__ == "__main__":
    main()
