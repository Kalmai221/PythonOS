#!/usr/bin/env python3
"""Dupes: find files that are exact copies of each other, and tidy them away without deleting anything.

    dupes ~/Pictures                 list the copies, with the space they waste
    dupes ~/Pictures --min 100       ignore files smaller than 100 KB (default 1 KB)
    dupes ~/Pictures --move          move every extra copy into ~/dupes-review (the first one of each set stays); asks first

Files are compared by size first, then by their SHA-256 fingerprint, so only real copies are listed.
"""
import hashlib
import os
import sys

from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm

console = Console()


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def fingerprint(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                return h.hexdigest()
            h.update(block)


def find_duplicates(folder, min_size=1024):
    """[[path, path, ...]] sets of identical files (each set oldest-name-first), biggest waste first."""
    by_size = {}
    for base, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(names):
            path = os.path.join(base, name)
            try:
                if os.path.islink(path):
                    continue
                size = os.path.getsize(path)
            except OSError:
                continue
            if size >= min_size:
                by_size.setdefault(size, []).append(path)
    groups = []
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_hash = {}
        for path in paths:
            try:
                by_hash.setdefault(fingerprint(path), []).append(path)
            except OSError:
                continue
        groups += [sorted(p) for p in by_hash.values() if len(p) > 1]
    return sorted(groups, key=lambda g: os.path.getsize(g[0]) * (len(g) - 1), reverse=True)


def wasted(groups):
    return sum(os.path.getsize(g[0]) * (len(g) - 1) for g in groups)


def move_extras(groups, destination):
    """Move every copy but the first of each set into `destination` (renamed if the name is taken). Returns the number moved."""
    os.makedirs(destination, exist_ok=True)
    moved = 0
    for group in groups:
        for path in group[1:]:
            name, target, n = os.path.basename(path), None, 1
            target = os.path.join(destination, name)
            while os.path.exists(target):
                n += 1
                stem, ext = os.path.splitext(name)
                target = os.path.join(destination, f"{stem} ({n}){ext}")
            os.replace(path, target)
            moved += 1
    return moved


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    min_kb = 1.0
    if "--min" in argv:
        at = argv.index("--min")
        try:
            min_kb = float(argv[at + 1])
            args = [a for a in args if a != argv[at + 1]]
        except (IndexError, ValueError):
            console.print("[red]--min needs a number of KB[/red]")
            return 1
    if len(args) != 1 or not os.path.isdir(args[0]):
        console.print(__doc__)
        return 1
    folder = args[0]
    with console.status("Comparing files..."):
        groups = find_duplicates(folder, int(min_kb * 1024))
    if not groups:
        console.print("[green]No copies found.[/green]")
        return 0
    for i, group in enumerate(groups, 1):
        console.print(f"[bold]{i}.[/bold] {human(os.path.getsize(group[0]))} each, {len(group)} copies")
        for path in group:
            console.print("   " + escape(path))
    console.print(f"[bold]{sum(len(g) - 1 for g in groups)} extra copies waste {human(wasted(groups))}.[/bold]")
    if "--move" in argv:
        review = os.path.join(os.path.dirname(os.path.abspath(folder)), "dupes-review")
        if Confirm.ask(f"Move the extra copies into {review}? Nothing is deleted.", default=False):
            console.print(f"[green]Moved {move_extras(groups, review)} files. Look through them, then delete the folder yourself.[/green]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
