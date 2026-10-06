#!/usr/bin/env python3
"""Checks the apps that use pip libraries (marketplace API 2): units (pint) and imgview (Pillow, rich-pixels). Skipped when a library is missing."""
import importlib.util
import os
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def load(name):
    spec = importlib.util.spec_from_file_location("app_" + name, os.path.join(REPO, "online_packages", "utilities", name, "run.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    try:
        import pint  # noqa: F401
        have_pint = True
    except ImportError:
        have_pint = False
    if have_pint:
        units = load("units")
        assert units.split("5 miles to km") == ("5 miles", "km") and units.split("3 ft") == ("3 ft", None)
        assert units.number(8.046720000001) == "8.04672" and units.number(150.0) == "150" and units.number(1.5e-7) == "1.5e-7"
        value, problem = units.convert("5 miles to km")
        assert problem is None and value == "8.04672 km", value
        assert units.convert("20 degC to degF")[0].startswith("68 ")
        assert units.convert("100 km/h to mph")[0].startswith("62.13")
        assert units.convert("2 hours + 30 minutes to minutes")[0] == "150 min"
        assert "do not match" in units.convert("5 kg to metres")[1]
        assert "do not know the unit" in units.convert("5 flurbs to km")[1]
        assert units.convert("")[1] and units.find("furlong")[0] == ["furlong"]
        manifest = __import__("json").load(open(os.path.join(REPO, "online_packages", "utilities", "units", "data.json"), encoding="utf-8"))
        assert manifest["api"] == 2 and manifest["pip"] == ["pint"] and not manifest["lockdown_safe"]
    else:
        print("pint is not installed: units checks skipped")
    try:
        import PIL
        import rich_pixels  # noqa: F401
        have_images = True
    except ImportError:
        have_images = False
    if have_images:
        view = load("imgview")
        assert view.fit((200, 100), 100) == (100, 50) and view.fit((100, 100), 40) == (40, 40) and view.fit((100, 10), 50)[1] % 2 == 0
        assert view.fit((100, 400), 50, max_rows=10)[1] == 20
        from PIL import Image
        folder = tempfile.mkdtemp(prefix="pyos-img-")
        path = os.path.join(folder, "t.png")
        Image.new("RGBA", (8, 8), (255, 0, 0, 128)).save(path)
        image, info = view.load(path)
        assert "PNG" in info and "8 x 8" in info and image.mode == "RGBA"
        from rich.console import Console
        console = Console(force_terminal=True, color_system="truecolor", width=40, record=False)
        with console.capture() as shown:
            console.print(view.render(image, 8))
        assert "\x1b[" in shown.get(), "the picture must be drawn in colour"
        bad = os.path.join(folder, "bad.png")
        open(bad, "w").write("not an image")
        view.console = console
        view.fs = None                                                     # the app runs on its own here: no PythonOS sandbox for the temporary file
        with console.capture() as shown:
            assert view.execute([bad]) is False
        assert "cannot show it" in shown.get()
        assert PIL.__version__
    else:
        print("Pillow or rich-pixels is not installed: imgview checks skipped")
    print("pip apps: all checks passed")


if __name__ == "__main__":
    sys.exit(main() or 0)
