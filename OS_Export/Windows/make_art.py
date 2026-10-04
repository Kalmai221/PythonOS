"""Draws the installer artwork (wizard side panel, header badge, icon) so the repository carries no binary art.

    python make_art.py <output folder>

Writes PythonOS.ico, wizard-<w>x<h>.bmp (the welcome/finish side panel) and small-<n>.bmp (the page header badge)
in several sizes: Inno Setup picks the one that matches the screen's scaling. Needs Pillow.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

TOP, BOTTOM = (14, 20, 48), (52, 36, 112)          # night blue -> indigo
ACCENT, TEXT, DIM = (94, 234, 212), (240, 244, 255), (160, 172, 214)
WIZARD_SIZES = [(164, 314), (192, 386), (246, 459), (328, 628)]
SMALL_SIZES = [55, 64, 80, 110]
ICON_SIZES = [16, 24, 32, 48, 64, 128, 256]


def font(names, size):
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


BOLD = ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"]
REGULAR = ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]
MONO = ["consolab.ttf", "consola.ttf", "DejaVuSansMono-Bold.ttf"]


def gradient(w, h, top=TOP, bottom=BOTTOM):
    image = Image.new("RGB", (w, h), top)
    draw = ImageDraw.Draw(image)
    for y in range(h):
        t = y / max(1, h - 1)
        draw.line([(0, y), (w, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return image


def terminal_card(draw, box, scale):
    """A little terminal window: title bar with three dots and a '>_' prompt."""
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=round(10 * scale), fill=(8, 12, 30), outline=ACCENT, width=max(1, round(2 * scale)))
    bar = round(20 * scale)
    draw.rounded_rectangle((x0, y0, x1, y0 + bar), radius=round(10 * scale), fill=(30, 40, 84))
    draw.rectangle((x0 + 1, y0 + bar // 2, x1 - 1, y0 + bar), fill=(30, 40, 84))
    for i, colour in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        cx, cy, r = x0 + round(14 * scale) + i * round(14 * scale), y0 + bar // 2, max(2, round(4 * scale))
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colour)
    f = font(MONO, round(34 * scale))
    draw.text((x0 + round(16 * scale), y0 + bar + round(8 * scale)), ">_", font=f, fill=ACCENT)


def wizard(w, h):
    scale = w / 164
    image = gradient(w, h)
    draw = ImageDraw.Draw(image)
    # faint scan lines for a terminal feel
    for y in range(0, h, max(3, round(4 * scale))):
        draw.line([(0, y), (w, y)], fill=tuple(min(255, c + 6) for c in image.getpixel((0, y))))
    margin = round(16 * scale)
    terminal_card(draw, (margin, round(40 * scale), w - margin, round(122 * scale)), scale)
    draw.text((margin, round(146 * scale)), "PythonOS", font=font(BOLD, round(26 * scale)), fill=TEXT)
    draw.text((margin, round(180 * scale)), "A tiny operating system\nthat lives in your terminal.", font=font(REGULAR, round(11 * scale)),
              fill=DIM, spacing=round(3 * scale))
    draw.rectangle((margin, h - round(46 * scale), margin + round(28 * scale), h - round(44 * scale)), fill=ACCENT)
    draw.text((margin, h - round(38 * scale)), "github.com/Kalmai221", font=font(REGULAR, round(9 * scale)), fill=DIM)
    return image


def badge(size):
    image = gradient(size, size)
    draw = ImageDraw.Draw(image)
    f = font(MONO, round(size * 0.55))
    box = draw.textbbox((0, 0), ">_", font=f)
    draw.text(((size - (box[2] - box[0])) / 2 - box[0], (size - (box[3] - box[1])) / 2 - box[1]), ">_", font=f, fill=ACCENT)
    return image


def icon(size):
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=round(size * 0.22), fill=(10, 14, 36, 255))
    g = gradient(size, size).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((round(size * 0.04),) * 2 + (size - round(size * 0.04),) * 2, radius=round(size * 0.2), fill=255)
    image.paste(g, (0, 0), mask)
    draw = ImageDraw.Draw(image)
    f = font(MONO, round(size * 0.52))
    box = draw.textbbox((0, 0), ">_", font=f)
    draw.text(((size - (box[2] - box[0])) / 2 - box[0], (size - (box[3] - box[1])) / 2 - box[1]), ">_", font=f, fill=ACCENT + (255,))
    return image


def main(out):
    os.makedirs(out, exist_ok=True)
    for w, h in WIZARD_SIZES:
        wizard(w, h).save(os.path.join(out, f"wizard-{w}x{h}.bmp"))
    for n in SMALL_SIZES:
        badge(n).save(os.path.join(out, f"small-{n}.bmp"))
    icon(256).save(os.path.join(out, "PythonOS.ico"), sizes=[(s, s) for s in ICON_SIZES])
    print("Installer art written to", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "installer-art")
