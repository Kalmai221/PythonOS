#!/usr/bin/env python3
"""Disk usage explorer (like ncdu): see what is taking up space in the PythonOS filesystem. Folders are listed biggest first with a bar;
open a folder by number, go up, and delete things you no longer need (with confirmation). It only shows what your account may see.
Commands: N (open folder), u (up), d N (delete), s (sort by size/name), r (rescan), t (top 20 biggest files), q (quit).
Usage: diskusage [folder]"""
import os
import shutil
import sys

from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm
from rich.table import Table

from pyos import fs

console = Console()
MAX_ENTRIES = 300_000


def size_text(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def tree_size(path, budget):
    """(bytes, files counted, truncated). budget is a one-element list: how many more files may be examined."""
    total = 0
    if os.path.isfile(path):
        try:
            return os.path.getsize(path), 1, False
        except OSError:
            return 0, 1, False
    count = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
        for name in files:
            if budget[0] <= 0:
                return total, count, True
            budget[0] -= 1
            count += 1
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total, count, False


def scan(folder):
    """[(name, is_dir, bytes, truncated)] for the entries of folder, biggest first."""
    budget = [MAX_ENTRIES]
    rows = []
    try:
        names = os.listdir(folder)
    except OSError:
        return rows
    for name in names:
        full = os.path.join(folder, name)
        is_dir = os.path.isdir(full) and not os.path.islink(full)
        size, _count, truncated = tree_size(full, budget) if not os.path.islink(full) else (0, 0, False)
        rows.append((name, is_dir, size, truncated))
    return rows


def biggest_files(folder, limit=20):
    found = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
        for name in files:
            full = os.path.join(root, name)
            try:
                found.append((os.path.getsize(full), full))
            except OSError:
                pass
        if len(found) > MAX_ENTRIES:
            break
    return sorted(found, reverse=True)[:limit]


class Explorer:
    def __init__(self, start):
        self.root = fs.BASE_DIR
        self.cwd = start
        self.by_size = True
        self.rows = []

    def refresh(self):
        rows = scan(self.cwd)
        self.rows = sorted(rows, key=(lambda r: -r[2]) if self.by_size else (lambda r: r[0].lower()))

    def show(self):
        total = sum(r[2] for r in self.rows) or 1
        table = Table(title=f"{fs.display(self.cwd, tilde=True)}  -  {size_text(sum(r[2] for r in self.rows))}", header_style="bold blue",
                      title_justify="left")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Size", justify="right")
        table.add_column("", no_wrap=True)
        table.add_column("Name")
        for i, (name, is_dir, size, truncated) in enumerate(self.rows[:60], 1):
            share = size / total
            table.add_row(str(i), size_text(size) + ("+" if truncated else ""), "[cyan]" + "#" * int(round(share * 20)) + "[/cyan]" + "[dim]" + "." * (20 - int(round(share * 20))) + "[/dim]",
                          f"[bold blue]{escape(name)}/[/bold blue]" if is_dir else escape(name))
        console.print(table if self.rows else "[dim](empty)[/dim]")
        if len(self.rows) > 60:
            console.print(f"[dim]... and {len(self.rows) - 60} smaller items[/dim]")
        try:
            usage = shutil.disk_usage(self.root)
            console.print(f"[dim]Disk: {size_text(usage.free)} free of {size_text(usage.total)}[/dim]")
        except OSError:
            pass

    def handle(self, line):
        parts = line.split()
        if not parts:
            return True
        cmd = parts[0].lower()
        if cmd in ("q", "quit"):
            return False
        if cmd == "u":
            if os.path.normcase(self.cwd) != os.path.normcase(self.root):
                self.cwd = os.path.dirname(self.cwd)
                self.refresh()
        elif cmd == "s":
            self.by_size = not self.by_size
            self.refresh()
        elif cmd == "r":
            self.refresh()
        elif cmd == "t":
            for size, path in biggest_files(self.cwd):
                console.print(f"{size_text(size):>10}  {escape(fs.display(path, tilde=True))}", highlight=False)
        elif cmd == "d" and len(parts) > 1 and parts[1].isdigit() and 1 <= int(parts[1]) <= len(self.rows):
            name, is_dir, size, _ = self.rows[int(parts[1]) - 1]
            path = os.path.join(self.cwd, name)
            fs.resolve(fs.display(path), write=True)                      # permission check
            if Confirm.ask(f"Delete {'the folder' if is_dir else 'the file'} [bold]{escape(name)}[/bold] ({size_text(size)})? This cannot be undone", default=False):
                shutil.rmtree(path) if is_dir else os.remove(path)
                console.print("[green]Deleted.[/green]")
                self.refresh()
        elif cmd.isdigit() and 1 <= int(cmd) <= len(self.rows):
            name, is_dir, _size, _t = self.rows[int(cmd) - 1]
            if is_dir:
                self.cwd = os.path.join(self.cwd, name)
                self.refresh()
            else:
                console.print("[dim]That is a file; use d to delete it.[/dim]")
        else:
            console.print("[yellow]Type a number to open a folder, u (up), d N (delete), s (sort), t (top files), r (rescan), q (quit).[/yellow]")
        return True


def main(args):
    try:
        start = fs.resolve(args[0]) if args else (fs.home_dir(fs.current_user()[0]) if fs.current_user()[0] else fs.BASE_DIR)
    except PermissionError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        return
    if not os.path.isdir(start):
        console.print("[red]That is not a folder.[/red]")
        return
    explorer = Explorer(start)
    with console.status("Measuring..."):
        explorer.refresh()
    while True:
        explorer.show()
        try:
            line = input("du> ")
        except EOFError:
            return
        try:
            if not explorer.handle(line):
                return
        except (OSError, PermissionError) as e:
            console.print(f"[red]{escape(fs.errtext(e))}[/red]")


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
