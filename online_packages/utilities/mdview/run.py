#!/usr/bin/env python3
"""Markdown viewer: read your notes (and any .md or .txt file) with headings, lists, code and links nicely formatted.
Works with the Notes app: your notes in ~/notes show up here, and 'e' opens the built-in editor."""
import os
import re

from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.prompt import Prompt
from rich.table import Table

from pyos import fs

console = Console()
EXTENSIONS = (".md", ".markdown", ".txt")
MAX_BYTES = 500_000


def home():
    name = fs.current_user()[0]
    return fs.home_dir(name) if name else fs.BASE_DIR


def documents(folder=None):
    """[(relative label, full path)] for notes first, then every markdown/text file in the home folder."""
    base = folder or home()
    found = []
    for root, dirs, files in os.walk(base):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            if name.lower().endswith(EXTENSIONS) and not name.startswith("."):
                full = os.path.join(root, name)
                found.append((os.path.relpath(full, base).replace(os.sep, "/"), full))
    found.sort(key=lambda item: (not item[0].startswith("notes/"), item[0].lower()))
    return found


def read(path):
    with open(path, "rb") as f:
        raw = f.read(MAX_BYTES)
    return raw.decode("utf-8", errors="replace")


def outline(text):
    """Headings of a document as [(level, title)]."""
    return [(len(m.group(1)), m.group(2).strip()) for m in re.finditer(r"^(#{1,4})\s+(.+)$", text, re.M)]


def show(label, path):
    text = read(path)
    if path.lower().endswith(".txt") and not re.search(r"^(#{1,4}\s|[-*]\s|```)", text, re.M):
        text = text.replace("\n", "  \n")                 # plain notes: keep their line breaks
    with console.pager(styles=False) if len(text.splitlines()) > console.height - 4 else _nullcontext():
        console.print(Markdown(text, hyperlinks=True))
    heads = outline(text)
    if heads:
        console.print("[dim]Sections: " + " > ".join(escape(t) for _l, t in heads[:8]) + "[/dim]")


class _nullcontext:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def listing(items):
    table = Table(title="Your documents", header_style="bold blue")
    table.add_column("#", justify="right")
    table.add_column("File", style="cyan")
    table.add_column("Title", style="dim")
    for i, (label, path) in enumerate(items, 1):
        heads = outline(read(path)[:4000])
        first = heads[0][1] if heads else (read(path)[:60].strip().splitlines() or [""])[0]
        table.add_row(str(i), escape(label), escape(first[:50]))
    console.print(table)


def main(start=None):
    items = documents()
    if not items:
        console.print("[yellow]No notes or markdown files yet. Install the Notes app and write one, or create a .md file with 'edit'.[/yellow]")
        return
    if start:
        hits = [it for it in items if start.lower() in it[0].lower()]
        if hits:
            show(*hits[0])
            return
        console.print(f"[yellow]No document matches '{escape(start)}'.[/yellow]")
    while True:
        listing(items)
        choice = Prompt.ask("Number to read, (s)earch text, (e)dit, (q)uit", default="q").strip().lower()
        if choice == "q":
            return
        if choice == "s":
            term = Prompt.ask("Search for").strip().lower()
            hits = [(l, p) for l, p in items if term and term in read(p).lower()]
            console.print("Found in: " + (", ".join(escape(l) for l, _ in hits) if hits else "nothing"))
        elif choice == "e":
            num = Prompt.ask("Number to edit")
            if num.isdigit() and 1 <= int(num) <= len(items):
                try:
                    import importlib
                    importlib.import_module("commands.edit").execute([fs.display(items[int(num) - 1][1])])
                except ImportError:
                    console.print("[yellow]Use: edit <file>[/yellow]")
                items = documents()
        elif choice.isdigit() and 1 <= int(choice) <= len(items):
            show(*items[int(choice) - 1])
            Prompt.ask("[dim]Press Enter to go back[/dim]", default="")
        else:
            console.print("[yellow]Pick a number from the list.[/yellow]")


def execute(args=None):
    try:
        main(" ".join(args) if args else None)
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    import sys
    execute(sys.argv[1:])
