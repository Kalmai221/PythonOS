#!/usr/bin/env python3
"""Hex viewer: the bytes of a file.

    hexview photo.png
    hexview photo.png 256            start at byte 256 (decimal, or 0x100)
    hexview photo.png 0 64           64 bytes from the start
"""
import os
import sys

from rich.console import Console
from rich.markup import escape

try:
    from pyos import fs
except ImportError:                                        # run on its own, outside PythonOS
    fs = None

console = Console()
WIDTH = 16
DEFAULT_LENGTH = 512
MAX_LENGTH = 64 * 1024


def dump_lines(data, offset=0):
    """Lines like '00000010  48 65 6c 6c ...  |Hello ...|' for the bytes `data` that start at `offset` in the file."""
    lines = []
    for start in range(0, len(data), WIDTH):
        chunk = data[start:start + WIDTH]
        cells = [f"{b:02x}" for b in chunk]
        left = " ".join(cells[:8])
        right = " ".join(cells[8:])
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{offset + start:08x}  {left:<23}  {right:<23}  |{text}|")
    return lines


def number(text):
    try:
        return int(text, 16) if text.lower().startswith("0x") else int(text)
    except ValueError:
        return None


def execute(args=None):
    args = list(args or [])
    if not 1 <= len(args) <= 3:
        console.print("[bold red]Usage:[/bold red] hexview <file> [start [length]]")
        return False
    start = number(args[1]) if len(args) > 1 else 0
    length = number(args[2]) if len(args) > 2 else DEFAULT_LENGTH
    if start is None or length is None or start < 0 or length < 1:
        console.print("[bold red]hexview: start and length are numbers (decimal or 0x...).[/bold red]")
        return False
    length = min(length, MAX_LENGTH)
    try:
        path = fs.resolve(args[0]) if fs else os.path.expanduser(args[0])
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(start)
            data = f.read(length)
    except OSError as e:
        console.print(f"[bold red]hexview: {escape(args[0])}: {escape(fs.errtext(e) if fs else str(e))}[/bold red]")
        return False
    if not data:
        console.print(f"[yellow]Nothing there: the file is {size} bytes.[/yellow]")
        return False
    for line in dump_lines(data, start):
        console.print(line, markup=False, highlight=False)
    console.print(f"[dim]{len(data)} of {size} bytes shown, from offset {start} (0x{start:x})[/dim]")
    return True


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
