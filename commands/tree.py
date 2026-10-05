import os

from rich.console import Console

import pyos.fs as fs
from pyos import search

console = Console()
config = {"name": "tree", "description": "Show a directory tree: tree [-a] [-d] [-s] [-L depth] [path]"}

MAX_ENTRIES = 500


def human(size):
    for unit in ("B", "K", "M", "G"):
        if size < 1024 or unit == "G":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024


def execute(args=None):
    args = list(args or [])
    show_hidden = show_dirs_only = show_size = False
    depth, path, i = None, None, 0
    while i < len(args):
        a = args[i]
        if a == "-L" and i + 1 < len(args) and args[i + 1].isdigit():
            depth = max(1, int(args[i + 1]))
            i += 2
            continue
        if a.startswith("-") and len(a) > 1 and all(ch in "ads" for ch in a[1:]):
            show_hidden |= "a" in a
            show_dirs_only |= "d" in a
            show_size |= "s" in a
        elif path is None and not a.startswith("-"):
            path = a
        else:
            console.print("[bold red]Usage:[/bold red] tree \\[-a] \\[-d] \\[-s] \\[-L depth] \\[path]")
            return False
        i += 1
    try:
        root = fs.resolve(path) if path else fs.current_dir()
    except PermissionError as e:
        console.print(f"[bold red]tree: {fs.errtext(e)}[/bold red]")
        return False
    if not os.path.isdir(root):
        console.print("[bold red]tree: not a directory[/bold red]")
        return False

    count, folders, files = [0], [0], [0]
    console.print(fs.display(root, tilde=True), markup=False)

    def walk(directory, prefix, level):
        try:
            entries = sorted(os.listdir(directory), key=str.lower)
        except OSError:
            return
        entries = [e for e in entries if (show_hidden or not e.startswith("."))
                   and search.readable(os.path.join(directory, e))]
        if show_dirs_only:
            entries = [e for e in entries if os.path.isdir(os.path.join(directory, e))]
        entries.sort(key=lambda e: (not os.path.isdir(os.path.join(directory, e)), e.lower()))
        for i, name in enumerate(entries):
            if count[0] >= MAX_ENTRIES:
                return
            count[0] += 1
            last = i == len(entries) - 1
            full = os.path.join(directory, name)
            is_dir = os.path.isdir(full) and not os.path.islink(full)
            folders[0] += is_dir
            files[0] += not is_dir
            size = f"[{human(os.path.getsize(full))}] " if show_size and not is_dir else ""
            console.print(f"{prefix}{'`-- ' if last else '|-- '}{size}{name}{'/' if is_dir else ''}", markup=False, highlight=False)
            if is_dir and (depth is None or level < depth):
                walk(full, prefix + ("    " if last else "|   "), level + 1)

    walk(root, "", 1)
    if count[0] >= MAX_ENTRIES:
        console.print(f"... (stopped after {MAX_ENTRIES} entries; use -L to limit the depth)", markup=False)
    console.print(f"\n{folders[0]} folders, {files[0]} files", markup=False)
    return True
