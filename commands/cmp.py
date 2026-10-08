from rich.console import Console

import pyos.fs as fs
from pyos import textcmd

console = Console()
config = {"name": "cmp", "description": "Compare two files byte by byte (cmp <file1> <file2>); says nothing when they are the same."}
CHUNK = 1 << 20


def first_difference(path_a, path_b):
    """None when the files hold the same bytes, else (byte number, line number, 'differ' or the name that ended first: 'a' or 'b')."""
    byte = line = 1
    with open(path_a, "rb") as a, open(path_b, "rb") as b:
        while True:
            block_a, block_b = a.read(CHUNK), b.read(CHUNK)
            if not block_a and not block_b:
                return None
            for x, y in zip(block_a, block_b):
                if x != y:
                    return byte, line, "differ"
                byte += 1
                if x == 10:
                    line += 1
            if len(block_a) != len(block_b):
                shorter = "a" if len(block_a) < len(block_b) else "b"
                return byte, line, shorter


def execute(args=None):
    names = [a for a in (args or []) if not a.startswith("-")]
    if len(names) != 2:
        console.print("[bold red]Usage:[/bold red] cmp <file1> <file2>")
        return False
    try:
        paths = [fs.resolve(n) for n in names]
        found = first_difference(*paths)
    except Exception as e:                                             # noqa: BLE001 - say it the way every command does
        console.print(f"[bold red]cmp: {fs.errtext(e)}[/bold red]")
        return False
    if found is None:
        return True
    byte, line, kind = found
    if kind == "differ":
        textcmd.emit(f"{names[0]} {names[1]} differ: byte {byte}, line {line}")
    else:
        textcmd.emit(f"cmp: EOF on {names[0] if kind == 'a' else names[1]} after byte {byte - 1}")
    return False
