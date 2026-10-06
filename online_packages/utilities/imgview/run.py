#!/usr/bin/env python3
"""Image viewer: show a picture in the terminal, drawn in colour blocks, with Pillow and rich-pixels.

    imgview photo.jpg              fit the terminal width
    imgview photo.png 60           60 characters wide
    imgview photo.png --info       size, format and colours, without drawing it
    imgview a.png b.png            several, one after another
It reads PNG, JPEG, GIF (the first frame), BMP, WebP and more. Nothing is changed or saved.
"""
import os
import shutil
import sys

from rich.console import Console
from rich.markup import escape

try:
    from pyos import fs
except ImportError:                                        # run on its own, outside PythonOS
    fs = None

console = Console()
MAX_PIXELS = 60_000_000                                    # refuse images that would need too much memory to decode


def path_of(name):
    return fs.resolve(name) if fs else os.path.expanduser(name)


def fit(size, columns, max_rows=None):
    """(width, height) in pixels for a picture of `size` drawn `columns` wide. Each character cell holds two pixels one above the other, so the
    height is kept in whole cells of two."""
    width, height = size
    columns = max(1, columns)
    scale = columns / width
    new_height = max(2, int(round(height * scale)))
    new_height += new_height % 2
    if max_rows and new_height > max_rows * 2:
        scale = (max_rows * 2) / height
        columns, new_height = max(1, int(width * scale)), max_rows * 2
    return columns, new_height


def describe(image, path):
    colours = image.getcolors(maxcolors=65536)
    return (f"{os.path.basename(path)}: {image.format or 'unknown format'}, {image.width} x {image.height} pixels, mode {image.mode}"
            + (f", {len(colours)} colours" if colours else ", more than 65,536 colours"))


def load(path):
    """The picture as an RGBA Pillow image (the first frame of an animation)."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    image = Image.open(path)
    info = describe(image, path)
    image.seek(0)
    return image.convert("RGBA"), info


def render(image, columns):
    from rich_pixels import Pixels
    from PIL import Image
    width, height = fit(image.size, columns)
    small = image.resize((width, height), Image.LANCZOS)
    background = Image.new("RGBA", small.size, (0, 0, 0, 255))          # transparent parts show as black
    return Pixels.from_image(Image.alpha_composite(background, small))


def execute(args=None):
    args = list(args or [])
    info_only = "--info" in args
    args = [a for a in args if a != "--info"]
    columns = shutil.get_terminal_size((80, 24)).columns - 1
    names = []
    for a in args:
        if a.isdigit():
            columns = max(8, min(int(a), 400))
        else:
            names.append(a)
    if not names:
        console.print("[bold red]Usage:[/bold red] imgview <image> [width] [--info]")
        return False
    try:
        import PIL  # noqa: F401
        import rich_pixels  # noqa: F401
    except ImportError:
        console.print("[bold red]imgview needs the Pillow and rich-pixels libraries. Install the app again: pkg install imgview[/bold red]")
        return False
    ok = True
    for name in names:
        try:
            image, info = load(path_of(name))
            if info_only:
                console.print(escape(info), highlight=False)
            else:
                console.print(render(image, columns))
                console.print(f"[dim]{escape(info)}[/dim]")
        except FileNotFoundError:
            console.print(f"[red]{escape(name)}: no such file[/red]")
            ok = False
        except PermissionError as e:
            console.print(f"[red]{escape(name)}: {escape(str(e))}[/red]")
            ok = False
        except Exception as e:                             # noqa: BLE001 - not an image, damaged, or too big
            console.print(f"[red]{escape(name)}: cannot show it ({escape(str(e)[:80])})[/red]")
            ok = False
    return ok


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
