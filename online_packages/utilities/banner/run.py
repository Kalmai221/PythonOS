#!/usr/bin/env python3
"""Banner: big letters from words (pyfiglet).

    banner Hello                      the standard font
    banner Hello -f slant             another font
    banner Hello -c green             in colour (red, green, yellow, blue, magenta, cyan)
    banner --fonts [word]             list the fonts, or those containing a word
"""
import sys

from rich.console import Console
from rich.text import Text

console = Console()
COLOURS = ("red", "green", "yellow", "blue", "magenta", "cyan", "white")


def fonts():
    import pyfiglet
    return sorted(pyfiglet.FigletFont.getFonts())


def render(text, font="standard", width=80):
    """The big-letter text for `text`. Raises ValueError for an unknown font."""
    import pyfiglet
    try:
        return pyfiglet.figlet_format(text, font=font, width=max(20, width)).rstrip("\n")
    except pyfiglet.FontNotFound as e:
        raise ValueError(f"there is no font called {font}") from e


def execute(args=None):
    args = list(args or [])
    try:
        import pyfiglet  # noqa: F401
    except ImportError:
        console.print("[bold red]banner needs the pyfiglet library. Install the app again: pkg install banner[/bold red]")
        return False
    if args[:1] == ["--fonts"]:
        names = [f for f in fonts() if not args[1:] or args[1].lower() in f.lower()]
        console.print(", ".join(names) if names else "[yellow]No font matches.[/yellow]", markup=False if names else True)
        return bool(names)
    font, colour = "standard", None
    for flag in ("-f", "-c"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                console.print("[bold red]Usage:[/bold red] banner <words> [-f font] [-c colour]")
                return False
            if flag == "-f":
                font = args[i + 1]
            else:
                colour = args[i + 1].lower()
            del args[i:i + 2]
    if not args:
        console.print("[bold red]Usage:[/bold red] banner <words> [-f font] [-c colour]   (banner --fonts lists the fonts)")
        return False
    if colour and colour not in COLOURS:
        console.print(f"[yellow]Colours: {', '.join(COLOURS)}[/yellow]")
        return False
    try:
        art = render(" ".join(args), font, console.width)
    except ValueError as e:
        console.print(f"[yellow]{e}. banner --fonts lists them.[/yellow]")
        return False
    console.print(Text(art, style=colour or ""), overflow="crop")
    return True


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
