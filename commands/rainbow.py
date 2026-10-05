from rich.console import Console
from rich.text import Text

from pyos import stdio

console = Console()
config = {"name": "rainbow", "description": "Colour piped text like a rainbow: ls | rainbow, fortune | rainbow"}

COLOURS = ["red", "dark_orange", "yellow", "green", "cyan", "blue", "magenta"]


def execute(args=None):
    text = " ".join(args) if args else (stdio.read_stdin() or "")
    if not text.strip():
        console.print("[bold red]Usage:[/bold red] <command> | rainbow   or   rainbow <text>")
        return False
    out = Text()
    i = 0
    for ch in text.rstrip("\n"):
        if ch.isspace():
            out.append(ch)
        else:
            out.append(ch, style=COLOURS[i % len(COLOURS)])
            i += 1
    console.print(out)
    return True
