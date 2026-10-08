import random

from rich.console import Console

from pyos import textcmd

console = Console()
config = {"name": "shuf", "description": "Shuffle lines (shuf [-n count] [file]); shuf -i 1-10 shuffles a range of numbers; shuf -e a b c shuffles the words."}


def parse_range(text):
    low, _dash, high = text.partition("-")
    try:
        first, last = int(low), int(high)
    except ValueError:
        raise ValueError("-i needs a range like 1-10") from None
    if last < first or last - first > 1_000_000:
        raise ValueError("-i needs a range like 1-10 (up to a million numbers)")
    return list(range(first, last + 1))


def shuffled(items, count=None, rng=random):
    """The items in random order (the first `count` of them if a count is given)."""
    items = list(items)
    rng.shuffle(items)
    return items[:count] if count is not None else items


def execute(args=None):
    args = list(args or [])
    echo = "-e" in args
    if echo:
        args.remove("-e")
    options, rest = textcmd.flags(args, with_value="ni")
    try:
        count = int(options["n"]) if options.get("n") else None
        if count is not None and count < 0:
            raise ValueError("-n needs a number of 0 or more")
        if options.get("i"):
            items = [str(n) for n in parse_range(options["i"])]
        elif echo:
            items = rest
        else:
            items = textcmd.read_lines(rest, "shuf")
            if items is None:
                return False
    except ValueError as e:
        console.print(f"[bold red]shuf: {e}[/bold red]")
        return False
    for line in shuffled(items, count):
        textcmd.emit(line)
    return True
