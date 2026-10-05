import fnmatch
import os
import time

from rich.console import Console
from rich.markup import escape

import pyos.fs as fs
from pyos import search

console = Console()
config = {"name": "find", "description": "Find files: find [folder] [name] [-iname p] [-type f|d] [-size +10k] [-mtime -7] [-maxdepth N]"}

MAX_RESULTS = 500
USAGE = ("[bold red]Usage:[/bold red] find \\[folder] \\[pattern] \\[-name p] \\[-iname p] \\[-type f|d] \\[-size +10k|-2M] "
         "\\[-mtime -7|+30] \\[-maxdepth N] \\[-l]")


def parse(args):
    """-> (options dict, error text or None). A bare word is a name pattern, a first word that is a folder is where to look."""
    opts = {"start": None, "names": [], "inames": [], "type": None, "size": None, "mtime": None, "maxdepth": None, "long": False}
    args = list(args)
    i = 0
    try:
        while i < len(args):
            a = args[i]
            nxt = args[i + 1] if i + 1 < len(args) else None
            if a == "-name" and nxt is not None:
                opts["names"].append(nxt)
                i += 2
            elif a == "-iname" and nxt is not None:
                opts["inames"].append(nxt)
                i += 2
            elif a == "-type" and nxt in ("f", "d"):
                opts["type"] = nxt
                i += 2
            elif a == "-size" and nxt is not None:
                opts["size"] = search.parse_size(nxt)
                i += 2
            elif a == "-mtime" and nxt is not None:
                opts["mtime"] = search.parse_age(nxt)
                i += 2
            elif a == "-maxdepth" and nxt is not None and nxt.isdigit():
                opts["maxdepth"] = int(nxt)
                i += 2
            elif a == "-l":
                opts["long"] = True
                i += 1
            elif a.startswith("-") and len(a) > 1:
                return opts, f"unknown option {a}"
            elif opts["start"] is None and not any(ch in a for ch in "*?[") and _is_folder(a):
                opts["start"] = a
                i += 1
            else:
                opts["names"].append(a)
                i += 1
    except ValueError:
        return opts, "bad number in an option"
    return opts, None


def _is_folder(text):
    try:
        return os.path.isdir(fs.resolve(text))
    except PermissionError:
        return False


def pattern_of(p):
    return p if any(ch in p for ch in "*?[") else f"*{p}*"      # a plain word matches any name containing it


def matches(name, full, is_dir, opts, now):
    low = name.lower()
    if opts["names"] and not any(fnmatch.fnmatchcase(name, pattern_of(p)) or fnmatch.fnmatch(low, pattern_of(p).lower()) for p in opts["names"]):
        return False
    if opts["inames"] and not any(fnmatch.fnmatch(low, pattern_of(p).lower()) for p in opts["inames"]):
        return False
    if opts["type"] == "f" and is_dir or opts["type"] == "d" and not is_dir:
        return False
    try:
        st = os.stat(full)
    except OSError:
        return False
    if opts["size"] and not is_dir and not search.compare(opts["size"][0], st.st_size, opts["size"][1]):
        return False
    if opts["size"] and is_dir:
        return False
    if opts["mtime"] and not search.compare(opts["mtime"][0], (now - st.st_mtime) / 86400, opts["mtime"][1]):
        return False
    return True


def execute(args=None):
    opts, error = parse(args or [])
    if error or not (opts["names"] or opts["inames"] or opts["type"] or opts["size"] or opts["mtime"]):
        if error:
            console.print(f"[bold red]find: {escape(error)}[/bold red]")
        console.print(USAGE)
        return False
    try:
        start = fs.resolve(opts["start"] or ".")
    except PermissionError as e:
        console.print(f"[bold red]find: {escape(fs.errtext(e))}[/bold red]")
        return False
    if not os.path.isdir(start):
        console.print(f"[bold red]find: {escape(opts['start'] or '.')}: not a folder[/bold red]")
        return False

    found, now = 0, time.time()
    for full, _depth, is_dir in search.walk(start, max_depth=opts["maxdepth"]):
        if not matches(os.path.basename(full), full, is_dir, opts, now):
            continue
        found += 1
        shown = escape(fs.display(full, tilde=True)) + ("/" if is_dir else "")
        if opts["long"]:
            st = os.stat(full)
            shown = f"{'-' if not is_dir else 'd'} {st.st_size:>9}  {time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime))}  {shown}"
        console.print(shown, highlight=False)
        if found >= MAX_RESULTS:
            console.print(f"[dim]... stopped after {MAX_RESULTS} results (narrow it with -type, -name or -maxdepth)[/dim]")
            return True
    if not found:
        console.print("[yellow]No matches.[/yellow]")
    return found > 0
