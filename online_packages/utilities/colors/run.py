#!/usr/bin/env python3
"""Colors: look at a colour, convert it, and find matching ones.

    colors #ff8800                  hex, rgb, hsl and hsv, plus the closest named colour
    colors rgb 255 136 0
    colors hsl 32 100 50
    colors coral                    by name
    colors palette #3366cc          complementary, triad and shades
"""
import colorsys
import re
import sys

from rich.console import Console
from rich.markup import escape
from rich.text import Text

console = Console()

NAMED = {
    "black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0), "lime": (0, 255, 0), "blue": (0, 0, 255), "yellow": (255, 255, 0),
    "cyan": (0, 255, 255), "magenta": (255, 0, 255), "silver": (192, 192, 192), "gray": (128, 128, 128), "maroon": (128, 0, 0),
    "olive": (128, 128, 0), "green": (0, 128, 0), "purple": (128, 0, 128), "teal": (0, 128, 128), "navy": (0, 0, 128), "orange": (255, 165, 0),
    "coral": (255, 127, 80), "salmon": (250, 128, 114), "gold": (255, 215, 0), "khaki": (240, 230, 140), "pink": (255, 192, 203),
    "hotpink": (255, 105, 180), "crimson": (220, 20, 60), "tomato": (255, 99, 71), "chocolate": (210, 105, 30), "tan": (210, 180, 140),
    "brown": (165, 42, 42), "turquoise": (64, 224, 208), "skyblue": (135, 206, 235), "steelblue": (70, 130, 180), "royalblue": (65, 105, 225),
    "indigo": (75, 0, 130), "violet": (238, 130, 238), "orchid": (218, 112, 214), "lavender": (230, 230, 250), "beige": (245, 245, 220),
    "ivory": (255, 255, 240), "mint": (189, 252, 201), "forestgreen": (34, 139, 34), "seagreen": (46, 139, 87), "limegreen": (50, 205, 50),
    "slategray": (112, 128, 144), "darkorange": (255, 140, 0), "firebrick": (178, 34, 34), "plum": (221, 160, 221),
}


def parse(args):
    """['#ff8800'] | ['rgb', '255', '136', '0'] | ['hsl', '32', '100', '50'] | ['coral'] -> (r, g, b). Raises ValueError."""
    text = " ".join(args).strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{6}|[0-9a-f]{3})|([0-9a-f]{6})", text)          # 3 digits need the #: "bad" or "add" could be words
    if m and text not in NAMED:
        h = m.group(1) or m.group(2)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", text)]
    if text.startswith("rgb") and len(nums) == 3:
        if not all(0 <= n <= 255 for n in nums):
            raise ValueError("rgb values are 0 to 255")
        return tuple(int(n) for n in nums)
    if text.startswith("hsl") and len(nums) == 3:
        h, s, l = nums[0] % 360 / 360, min(max(nums[1], 0), 100) / 100, min(max(nums[2], 0), 100) / 100
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return tuple(round(c * 255) for c in (r, g, b))
    key = text.replace(" ", "")
    if key in NAMED:
        return NAMED[key]
    raise ValueError(f"'{text}' is not a colour - try #ff8800, rgb 255 136 0, hsl 32 100 50 or a name like coral")


def to_hex(rgb):
    return "#%02x%02x%02x" % rgb


def to_hsl(rgb):
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    return round(h * 360) % 360, round(s * 100), round(l * 100)


def to_hsv(rgb):
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    return round(h * 360) % 360, round(s * 100), round(v * 100)


def nearest_name(rgb):
    """The closest named colour (by weighted distance, which follows what the eye notices better than a plain one)."""
    def distance(other):
        rm = (rgb[0] + other[0]) / 2
        dr, dg, db = rgb[0] - other[0], rgb[1] - other[1], rgb[2] - other[2]
        return (2 + rm / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rm) / 256) * db * db
    return min(NAMED, key=lambda name: distance(NAMED[name]))


def rotate(rgb, degrees):
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    r, g, b = colorsys.hls_to_rgb((h + degrees / 360) % 1, l, s)
    return tuple(round(c * 255) for c in (r, g, b))


def shade(rgb, factor):
    """factor < 1 darkens, > 1 lightens (towards white)."""
    if factor <= 1:
        return tuple(round(c * factor) for c in rgb)
    return tuple(round(c + (255 - c) * (factor - 1)) for c in rgb)


def swatch(rgb, label=""):
    text = Text("      ", style=f"on {to_hex(rgb)}")
    text.append(f"  {to_hex(rgb)} {label}")
    return text


def main(argv):
    if not argv:
        console.print(__doc__)
        return 1
    palette = argv[0].lower() == "palette"
    try:
        rgb = parse(argv[1:] if palette else argv)
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    if palette:
        for label, c in (("the colour", rgb), ("complement", rotate(rgb, 180)), ("triad", rotate(rgb, 120)), ("triad", rotate(rgb, 240)),
                         ("analogous", rotate(rgb, 30)), ("analogous", rotate(rgb, -30)), ("darker", shade(rgb, 0.6)), ("lighter", shade(rgb, 1.5))):
            console.print(swatch(c, label))
        return 0
    console.print(swatch(rgb, f"({nearest_name(rgb)})"))
    console.print(f"  hex  {to_hex(rgb)}\n  rgb  {rgb[0]} {rgb[1]} {rgb[2]}\n  hsl  {to_hsl(rgb)[0]} {to_hsl(rgb)[1]}% {to_hsl(rgb)[2]}%\n"
                  f"  hsv  {to_hsv(rgb)[0]} {to_hsv(rgb)[1]}% {to_hsv(rgb)[2]}%")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
