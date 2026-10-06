import os

import pyos.fs as fs
from pyos import textcmd

config = {"name": "du", "description": "How much space folders use (du [-s] [-h] [path])."}


def human(n):
    for unit in ("B", "K", "M", "G"):
        if n < 1024 or unit == "G":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


def sizes(root):
    """{folder: total bytes including everything below}, for `root` and every folder inside it."""
    totals = {}
    for folder, _dirs, files in os.walk(root, topdown=False):
        total = 0
        for name in files:
            try:
                total += os.path.getsize(os.path.join(folder, name))
            except OSError:
                pass
        total += sum(totals.get(os.path.join(folder, d), 0) for d in _dirs)
        totals[folder] = total
    return totals


def execute(args=None):
    options, rest = textcmd.flags(args)
    target = fs.resolve(rest[0]) if rest else fs.current_dir()
    if not os.path.exists(target):
        textcmd.console.print(f"[bold red]du: {rest[0] if rest else target}: no such file or folder[/bold red]")
        return False
    if os.path.isfile(target):
        textcmd.emit(f"{human(os.path.getsize(target)) if 'h' in options else os.path.getsize(target)}\t{fs.display(target, tilde=True)}")
        return True
    totals = sizes(target)
    shown = [target] if "s" in options else sorted(totals)
    for folder in shown:
        size = totals[folder]
        textcmd.emit(f"{human(size) if 'h' in options else size}\t{fs.display(folder, tilde=True)}")
    return True
