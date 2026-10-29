#!/usr/bin/env python3
"""Render screens to PNG (LED look) without the panel: preview.py [screen ...] [--fake-flight]"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ledwall.app import App, load_config  # noqa: E402
from ledwall.render import led_preview  # noqa: E402

FAKE = {"hex": "4b1805", "callsign": "EZS1435", "t": "A320", "r": "HB-JXA", "alt_baro": 7400,
        "track": 225.0, "dist_km": 3.2, "gs": 260,
        "route": {"airline_code": "EZS", "_airport_codes_iata": "GVA-SUF"}}

ap = argparse.ArgumentParser()
ap.add_argument("screens", nargs="*")
ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "preview"))
ap.add_argument("--fake-flight", action="store_true", help="inject a sample aircraft")
ap.add_argument("--at", type=float, default=0, help="seconds offset for scroll position")
args = ap.parse_args()

app = App(load_config())
app.weather.refresh()
if args.fake_flight:
    app.adsb.aircraft, app.adsb.updated = [FAKE], time.time()
else:
    app.adsb.refresh()
out = Path(args.out)
out.mkdir(exist_ok=True)
for name in args.screens or list(app.screens):
    s = app.screens[name]
    if not s.ready():
        print(f"{name}: no data")
        continue
    img, _ = s.render(time.time() + args.at)
    led_preview(img).save(out / f"{name}.png")
    img.save(out / f"{name}_raw.png")
    print(out / f"{name}.png")
