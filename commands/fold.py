import textwrap

from rich.console import Console

from pyos import textcmd

console = Console()
config = {"name": "fold", "description": "Wrap long lines (fold [-w width] [-s] [file]); -s breaks at spaces instead of in the middle of words."}


def wrap_line(line, width=80, at_spaces=False):
    """The pieces of one line, each at most `width` characters."""
    if len(line) <= width:
        return [line]
    if at_spaces:
        return textwrap.wrap(line, width, break_long_words=True, break_on_hyphens=False, drop_whitespace=False, replace_whitespace=False) or [""]
    return [line[i:i + width] for i in range(0, len(line), width)]


def execute(args=None):
    options, files = textcmd.flags(args, with_value="w")
    try:
        width = int(options.get("w") or 80)
        if width < 1:
            raise ValueError
    except ValueError:
        console.print("[bold red]fold: -w needs a number of at least 1[/bold red]")
        return False
    lines = textcmd.read_lines(files, "fold")
    if lines is None:
        return False
    for line in lines:
        for piece in wrap_line(line, width, bool(options.get("s"))):
            textcmd.emit(piece)
    return True
