"""Canvas helpers: pixel fonts, text layout, RGB565 packing."""
import os
from pathlib import Path

from PIL import BdfFontFile, Image, ImageDraw, ImageFont

W, H = 64, 32   # logical canvas the screens draw on; scaled up to the panel in to_rgb565
FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
FONT_CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "ledwall" / "fonts"

_fonts: dict[str, ImageFont.ImageFont] = {}


def font(name: str) -> ImageFont.ImageFont:
    """Load fonts/<name>.bdf, converting it to PIL's bitmap format once."""
    if name not in _fonts:
        src = FONT_DIR / f"{name}.bdf"
        pil = FONT_CACHE / f"{name}.pil"
        if not pil.exists() or pil.stat().st_mtime < src.stat().st_mtime:
            FONT_CACHE.mkdir(parents=True, exist_ok=True)
            with open(src, "rb") as fp:
                BdfFontFile.BdfFontFile(fp).save(str(FONT_CACHE / name))
        _fonts[name] = ImageFont.load(str(pil))
    return _fonts[name]


def canvas(size: tuple[int, int] = (W, H)) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", size)
    return img, ImageDraw.Draw(img)


def text_width(s: str, f) -> int:
    return int(f.getlength(s))


def text(d: ImageDraw.ImageDraw, x: int, y: int, s: str, f, fill, anchor: str = "l") -> int:
    """Draw s with its cell top at y. anchor l/c/r is horizontal. Returns the width."""
    w = text_width(s, f)
    if anchor == "c":
        x -= w // 2
    elif anchor == "r":
        x -= w
    d.text((x, y), s, font=f, fill=fill)
    return w


def text_fit(d: ImageDraw.ImageDraw, x: int, y: int, w: int, s: str, fonts: list[str], fill) -> int:
    """Draw s in a w-wide box without moving text: the first font in `fonts` it fits in,
    else the last font, cut to the box (whole characters). Returns the width drawn."""
    for name in fonts:
        f = font(name)
        if text_width(s, f) <= w:
            return text(d, x, y, s, f, fill)
    while s and text_width(s, f) > w:
        s = s[:-1]
    return text(d, x, y, s.rstrip(), f, fill)


def to_rgb565(img: Image.Image, size: tuple[int, int] = (W, H)) -> bytes:
    """Pack for the panel, scaling the canvas up (nearest) to the panel's size."""
    if img.size != size:
        img = img.resize(size, Image.Resampling.NEAREST)
    raw = img.convert("RGB").tobytes()
    out = bytearray(size[0] * size[1] * 2)
    j = 0
    for i in range(0, len(raw), 3):
        v = ((raw[i] & 0xF8) << 8) | ((raw[i + 1] & 0xFC) << 3) | (raw[i + 2] >> 3)
        out[j] = v & 0xFF
        out[j + 1] = v >> 8
        j += 2
    return bytes(out)


def led_preview(img: Image.Image, scale: int = 10) -> Image.Image:
    """Upscale to look like the panel: round-ish LEDs on black."""
    w, h = img.size
    big = Image.new("RGB", (w * scale, h * scale), (8, 8, 8))
    d = ImageDraw.Draw(big)
    px = img.load()
    m = max(1, scale // 6)
    for y in range(h):
        for x in range(w):
            c = px[x, y]
            if c != (0, 0, 0):
                d.ellipse((x * scale + m, y * scale + m, (x + 1) * scale - m - 1, (y + 1) * scale - m - 1), fill=c)
    return big
