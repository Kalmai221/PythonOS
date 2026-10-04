import fnmatch
import os
from rich.console import Console
from rich.markup import escape
import pyos.fs as fs

console = Console()
config = {"name": "find", "description": "Find files by name: find <pattern> [folder]  (for example: find *.txt ~/docs)"}

MAX_RESULTS = 500


def execute(args=None):
    args = list(args or [])
    if not args:
        console.print("[bold red]Usage:[/bold red] find <pattern> \\[folder]")
        return False
    pattern = args[0]
    try:
        start = fs.resolve(args[1] if len(args) > 1 else ".")
    except PermissionError as e:
        console.print(f"[bold red]find: {escape(str(e))}[/bold red]")
        return False
    if not os.path.isdir(start):
        console.print(f"[bold red]find: {escape(args[1] if len(args) > 1 else '.')}: not a folder[/bold red]")
        return False
    if not any(ch in pattern for ch in "*?["):
        pattern = f"*{pattern}*"             # a plain word matches any name containing it

    found = 0
    for dirpath, dirnames, filenames in os.walk(start):
        dirnames[:] = sorted(d for d in dirnames if not os.path.islink(os.path.join(dirpath, d)))
        for name in sorted(dirnames + filenames):
            full = os.path.join(dirpath, name)
            try:
                fs._check_permission(full, False)          # skip what the user may not look at
            except PermissionError:
                continue
            if fnmatch.fnmatch(name.lower(), pattern.lower()):
                found += 1
                suffix = "/" if os.path.isdir(full) else ""
                console.print(escape(fs.display(full, tilde=True)) + suffix, highlight=False)
                if found >= MAX_RESULTS:
                    console.print(f"[dim]... stopped after {MAX_RESULTS} results[/dim]")
                    return True
    if not found:
        console.print("[yellow]No matches.[/yellow]")
    return found > 0
