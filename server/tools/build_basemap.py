#!/usr/bin/env python3
"""Build server/data/basemap.json: lake shores and land borders in Swiss LV95 metres,
clipped to the MeteoSwiss radar domain, for the radar widget's background.

Source: Natural Earth 10m lakes, lakes_europe and admin_0 boundary lines (public domain).
Usage: build_basemap.py <dir with the three .geojson files>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ledwall.geo import lv95  # noqa: E402

X0, X1, Y0, Y1 = 2_255_000, 2_965_000, 840_000, 1_480_000  # radar (CCS4) domain
STEP = 300  # drop vertices closer than this (metres) to the previous kept one


def lines(geom: dict):
    t, c = geom["type"], geom["coordinates"]
    if t == "LineString":
        yield c
    elif t in ("MultiLineString", "Polygon"):
        yield from c
    elif t == "MultiPolygon":
        for poly in c:
            yield from poly


def convert(coords) -> list[list[int]]:
    out = []
    for lon, lat in coords:
        x, y = lv95(lon, lat)
        if out and abs(x - out[-1][0]) < STEP and abs(y - out[-1][1]) < STEP:
            continue
        out.append([round(x), round(y)])
    return out


def inside(line) -> bool:
    return any(X0 <= x <= X1 and Y0 <= y <= Y1 for x, y in line)


def main(src: Path):
    lakes, seen = [], set()
    for f in ("ne_10m_lakes_europe", "ne_10m_lakes"):
        for ft in json.load(open(src / f"{f}.geojson"))["features"]:
            for ring in lines(ft["geometry"]):
                line = convert(ring)
                key = tuple(map(tuple, line[:3]))
                if len(line) > 3 and inside(line) and key not in seen:
                    seen.add(key)
                    lakes.append(line)
    borders = [line for ft in json.load(open(src / "ne_10m_admin_0_boundary_lines_land.geojson"))["features"]
               for raw in lines(ft["geometry"]) if len(line := convert(raw)) > 1 and inside(line)]
    out = Path(__file__).resolve().parent.parent / "data" / "basemap.json"
    out.write_text(json.dumps({"source": "Natural Earth (public domain), LV95 metres",
                               "lakes": lakes, "borders": borders}, separators=(",", ":")))
    print(out, len(lakes), "lake rings,", len(borders), "border lines,", out.stat().st_size, "bytes")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
