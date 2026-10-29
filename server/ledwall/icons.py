"""11x11 pixel-art weather icons for MeteoSwiss icon codes (1-42 day, 101-142 night)."""
from PIL import Image

PALETTE = {
    "Y": (255, 200, 0),     # sun
    "O": (255, 120, 0),     # sun rays
    "L": (230, 230, 160),   # moon
    "W": (200, 200, 215),   # cloud
    "G": (110, 110, 135),   # cloud shade
    "D": (120, 120, 140),   # dark cloud
    "E": (70, 70, 90),      # dark cloud shade
    "B": (40, 120, 255),    # rain
    "S": (255, 255, 255),   # snow
    "T": (255, 230, 0),     # lightning
    "F": (150, 150, 160),   # fog
}

SUN = [
    ".....O.....",
    ".O.......O.",
    "....YYY....",
    "...YYYYY...",
    "..YYYYYYY..",
    "O.YYYYYYY.O",
    "..YYYYYYY..",
    "...YYYYY...",
    "....YYY....",
    ".O.......O.",
    ".....O.....",
]
MOON = [
    "....LLL....",
    "...LLL.....",
    "..LLL......",
    "..LL.......",
    ".LLL.......",
    ".LLL.......",
    ".LLL.......",
    "..LL.......",
    "..LLL......",
    "...LLL.....",
    "....LLL....",
]
SUN_SMALL = [
    "...O...",
    ".O.Y.O.",
    "..YYY..",
    "OYYYYYO",
    "..YYY..",
    ".O.Y.O.",
    "...O...",
]
MOON_SMALL = [
    "..LLL..",
    ".LLL...",
    "LLL....",
    "LLL....",
    "LLL....",
    ".LLL...",
    "..LLL..",
]
CLOUD = [
    "....WWW....",
    "..WWWWWWW..",
    ".WWWWWWWWW.",
    "WWWWWWWWWWW",
    "WWWWWWWWWWW",
    ".GGGGGGGGG.",
]
DARK_CLOUD = [row.replace("W", "D").replace("G", "E") for row in CLOUD]
RAIN = [
    "..B...B...B",
    ".B...B...B.",
    "B...B...B..",
]
SNOW = [
    ".S...S...S.",
    "...S...S...",
    ".S...S...S.",
]
SLEET = [
    "..B...S...B",
    ".B...B...B.",
    "S...S...S..",
]
BOLT = [
    "..TT",
    ".TT.",
    "TTTT",
    ".TT.",
    ".T..",
]
FOG = [
    "...........",
    "FFFFFFFF...",
    "...........",
    "..FFFFFFFFF",
    "...........",
    "FFFFFFFFFF.",
    "...........",
    "..FFFFFFFF.",
    "...........",
    "FFFFFFFF...",
]

# Coarse mapping of MeteoSwiss day codes to (sky, precipitation).
# sky: clear | partly | cloudy | showers (sun + cloud + precip) | fog
_CODES: dict[int, tuple[str, str | None]] = {}
for c in (1,):
    _CODES[c] = ("clear", None)
for c in (2, 3, 26):
    _CODES[c] = ("partly", None)
for c in (4, 5, 27, 35):
    _CODES[c] = ("cloudy", None)
for c in (28,):
    _CODES[c] = ("fog", None)
for c in (6, 29, 32, 33):
    _CODES[c] = ("showers", "rain")
for c in (7, 31):
    _CODES[c] = ("showers", "sleet")
for c in (8, 30, 34):
    _CODES[c] = ("showers", "snow")
for c in (12, 36, 37):
    _CODES[c] = ("showers", "thunder")
for c in (9, 14, 17, 20):
    _CODES[c] = ("cloudy", "rain")
for c in (10, 15, 18, 21):
    _CODES[c] = ("cloudy", "sleet")
for c in (11, 16, 19, 22):
    _CODES[c] = ("cloudy", "snow")
for c in (13, 23, 24, 25, 38, 39, 40, 41, 42):
    _CODES[c] = ("cloudy", "thunder")


def _blit(img: Image.Image, x: int, y: int, art: list[str]):
    px = img.load()
    for dy, row in enumerate(art):
        for dx, ch in enumerate(row):
            if ch != "." and 0 <= x + dx < img.width and 0 <= y + dy < img.height:
                px[x + dx, y + dy] = PALETTE[ch]


def draw_icon(img: Image.Image, x: int, y: int, code: int | None):
    """Draw the 11x11 icon for a MeteoSwiss code with its top-left at (x, y)."""
    if code is None:
        return
    night = code > 100
    sky, precip = _CODES.get(code % 100, ("cloudy", None))
    big, small = (MOON, MOON_SMALL) if night else (SUN, SUN_SMALL)
    if sky == "clear":
        _blit(img, x, y, big)
    elif sky == "partly":
        _blit(img, x, y, small)
        _blit(img, x, y + 5, CLOUD)
    elif sky == "fog":
        _blit(img, x, y, FOG)
    elif precip is None:  # cloudy, dry: two layered clouds
        _blit(img, x, y + 1, DARK_CLOUD)
        _blit(img, x, y + 5, CLOUD)
    else:
        if sky == "showers":
            _blit(img, x + 4, y, small)
        _blit(img, x, y + 2, DARK_CLOUD if precip == "thunder" else CLOUD)
        if precip == "thunder":
            _blit(img, x + 4, y + 6, BOLT)
        else:
            _blit(img, x, y + 8, {"rain": RAIN, "snow": SNOW, "sleet": SLEET}[precip])
