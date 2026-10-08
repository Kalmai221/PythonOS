import uuid

from rich.console import Console

from pyos import textcmd

console = Console()
config = {"name": "uuidgen", "description": "Make random identifiers (uuidgen [-n count] [-t] [--upper]); -t makes time-based ones."}


def make(count=1, time_based=False, upper=False):
    """`count` UUIDs as text (random version 4, or version 1 from the clock and this computer)."""
    ids = [str(uuid.uuid1() if time_based else uuid.uuid4()) for _ in range(count)]
    return [i.upper() for i in ids] if upper else ids


def execute(args=None):
    options, rest = textcmd.flags(args, with_value="n")
    try:
        count = int(options.get("n") or (rest[0] if rest else 1))
        if not 1 <= count <= 1000:
            raise ValueError
    except ValueError:
        console.print("[bold red]uuidgen: the count must be a number from 1 to 1000[/bold red]")
        return False
    for line in make(count, bool(options.get("t")), "--upper" in (args or []) or bool(options.get("u"))):
        textcmd.emit(line)
    return True
