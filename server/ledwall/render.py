"""Canvas helpers: pixel fonts, text layout, RGB565 packing."""
import os
from pathlib import Path

from PIL import BdfFontFile, Image, ImageDraw, ImageFont

W, H = 64, 32
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


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H))
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


def text_fit(img: Image.Image, x: int, y: int, w: int, s: str, f, fill, t: float,
             speed: float = 18.0, h: int = 10) -> bool:
    """Draw s in a w-wide box; scroll it if it doesn't fit. Returns True while scrolling."""
    tw = text_width(s, f)
    if tw <= w:
        ImageDraw.Draw(img).text((x, y), s, font=f, fill=fill)
        return False
    gap = 12
    period = tw + gap
    pause = 1.5  # hold the start of the text before scrolling
    phase = t % (period / speed + pause)
    off = 0 if phase < pause else int((phase - pause) * speed)
    strip = Image.new("RGB", (w, h))
    sd = ImageDraw.Draw(strip)
    sd.text((-off, 0), s, font=f, fill=fill)
    sd.text((-off + period, 0), s, font=f, fill=fill)
    img.paste(strip, (x, y))
    return True


def to_rgb565(img: Image.Image) -> bytes:
    raw = img.convert("RGB").tobytes()
    out = bytearray(W * H * 2)
    j = 0
    for i in range(0, len(raw), 3):
        v = ((raw[i] & 0xF8) << 8) | ((raw[i + 1] & 0xFC) << 3) | (raw[i + 2] >> 3)
        out[j] = v & 0xFF
        out[j + 1] = v >> 8
        j += 2
    return bytes(out)


def led_preview(img: Image.Image, scale: int = 10) -> Image.Image:
    """Upscale to look like the panel: round-ish LEDs on black."""
    big = Image.new("RGB", (W * scale, H * scale), (8, 8, 8))
    d = ImageDraw.Draw(big)
    px = img.load()
    m = max(1, scale // 6)
    for y in range(H):
        for x in range(W):
            c = px[x, y]
            if c != (0, 0, 0):
                d.ellipse((x * scale + m, y * scale + m, (x + 1) * scale - m - 1, (y + 1) * scale - m - 1), fill=c)
    return big
