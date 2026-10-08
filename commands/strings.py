import re

from rich.console import Console

import pyos.fs as fs
from pyos import textcmd

console = Console()
config = {"name": "strings", "description": "Show the readable text inside a file of any kind (strings [-n length] <file>)."}
LIMIT = 64 * 1024 * 1024


def found(data, minimum=4):
    """The runs of printable ASCII of at least `minimum` characters in some bytes."""
    return [m.group().decode("ascii") for m in re.finditer(rb"[\x20-\x7e\t]{%d,}" % minimum, data)]


def execute(args=None):
    options, files = textcmd.flags(args, with_value="n")
    try:
        minimum = int(options.get("n") or 4)
        if minimum < 1:
            raise ValueError
    except ValueError:
        console.print("[bold red]strings: -n needs a number of at least 1[/bold red]")
        return False
    if len(files) != 1:
        console.print("[bold red]Usage:[/bold red] strings [-n length] <file>")
        return False
    try:
        with open(fs.resolve(files[0]), "rb") as f:
            data = f.read(LIMIT)
    except Exception as e:                                             # noqa: BLE001 - say it the way every command does
        console.print(f"[bold red]strings: {files[0]}: {fs.errtext(e)}[/bold red]")
        return False
    for text in found(data, minimum):
        textcmd.emit(text)
    return True
