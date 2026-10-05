#!/usr/bin/env python3
"""Snippets: a clipboard and a library of named snippets. Snippets are ordinary files in ~/snippets, so you can also
cat, grep or edit them; the clipboard is ~/.clipboard, which works on every device (no system clipboard needed)."""
import os
import re
import sys
import time

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table

try:
    from pyos import appdata, fs, stdio
except ImportError:
    appdata = fs = stdio = None

console = Console()


def home():
    if fs:
        name = fs.current_user()[0]
        base = fs.home_dir(name) if name else fs.BASE_DIR
    else:
        base = os.path.join("files", "home")
    os.makedirs(base, exist_ok=True)
    return base


def snippet_dir():
    path = os.path.join(home(), "snippets")
    os.makedirs(path, exist_ok=True)
    return path


def clip_file():
    return os.path.join(home(), ".clipboard")


def safe_name(text):
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip()).strip("-.")[:60]
    return name


def names():
    return sorted(f for f in os.listdir(snippet_dir()) if os.path.isfile(os.path.join(snippet_dir(), f)))


def read(name):
    with open(os.path.join(snippet_dir(), name), encoding="utf-8") as f:
        return f.read()


def write(name, text):
    with open(os.path.join(snippet_dir(), name), "w", encoding="utf-8") as f:
        f.write(text)


def remember(text):
    """Keep what was copied in the clipboard history (the Clipboard History app shows it): newest first, 50 entries, no repeats."""
    if not appdata or not text.strip():
        return
    history = appdata.load("clip_history", []) or []
    history = [h for h in history if h.get("text") != text]
    history.insert(0, {"t": int(time.time()), "text": text[:5000]})
    appdata.save("clip_history", history[:50])


def read_clip():
    try:
        with open(clip_file(), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def read_multiline(prompt):
    console.print(f"[dim]{prompt} Finish with a line containing just a dot (.)[/dim]")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == ".":
            break
        lines.append(line)
    return "\n".join(lines)


def show_list():
    items = names()
    if not items:
        console.print("[dim]No snippets yet. Press 'a' to add one, or 's' to save the clipboard as one.[/dim]")
        return items
    table = Table(header_style="bold blue", title="Snippets")
    table.add_column("#", justify="right")
    table.add_column("Name", style="cyan")
    table.add_column("Preview", style="dim")
    for i, n in enumerate(items, 1):
        first = read(n).strip().splitlines()[:1]
        table.add_row(str(i), n, escape((first[0] if first else "")[:50]))
    console.print(table)
    return items


def pick(items, text):
    text = text.strip()
    if text.isdigit() and 1 <= int(text) <= len(items):
        return items[int(text) - 1]
    if text in items:
        return text
    matches = [n for n in items if text.lower() in n.lower()]
    return matches[0] if len(matches) == 1 else None


def show(name):
    text = read(name)
    ext = os.path.splitext(name)[1].lstrip(".") or "text"
    console.print(Panel(Syntax(text, ext if ext in ("py", "sh", "json", "md", "html", "js") else "text", word_wrap=True),
                        title=name, border_style="blue"))


def main():
    while True:
        items = show_list()
        clip = read_clip()
        console.print(f"[dim]Clipboard: {escape(clip[:40].replace(chr(10), ' ')) + ('...' if len(clip) > 40 else '') if clip else 'empty'}[/dim]")
        choice = Prompt.ask("(a)dd  (v)iew  (c)opy to clipboard  (s)ave clipboard  (p)aste out  (e)dit  (d)elete  (f)ind  (q)uit",
                            choices=["a", "v", "c", "s", "p", "e", "d", "f", "q"], default="q")
        if choice == "q":
            return
        if choice == "a":
            name = safe_name(Prompt.ask("Name"))
            if not name:
                continue
            write(name, read_multiline("Type or paste the snippet."))
            console.print(f"[green]Saved {name}.[/green]")
        elif choice == "s":
            name = safe_name(Prompt.ask("Name for the clipboard text"))
            if name and clip:
                write(name, clip)
                console.print(f"[green]Saved {name}.[/green]")
            elif not clip:
                console.print("[yellow]The clipboard is empty.[/yellow]")
        elif choice == "p":
            console.print(Panel(escape(clip) or "[dim]empty[/dim]", title="Clipboard", border_style="blue"))
        elif choice == "f":
            term = Prompt.ask("Search for").strip().lower()
            hits = [n for n in items if term in n.lower() or term in read(n).lower()]
            console.print("Found: " + (", ".join(hits) if hits else "nothing"))
        elif items:
            name = pick(items, Prompt.ask("Which snippet (number or name)"))
            if not name:
                console.print("[red]No such snippet.[/red]")
                continue
            if choice == "v":
                show(name)
            elif choice == "c":
                with open(clip_file(), "w", encoding="utf-8") as f:
                    f.write(read(name))
                remember(read(name))
                console.print(f"[green]Copied {name} to the clipboard.[/green]")
            elif choice == "e":
                write(name, read_multiline(f"New text for {name}."))
            elif choice == "d":
                if Prompt.ask(f"Delete {name}?", choices=["y", "n"], default="n") == "y":
                    os.remove(os.path.join(snippet_dir(), name))
                    console.print("[green]Deleted.[/green]")


def execute(args=None):
    args = list(args or [])
    try:
        if not args:
            main()
        elif args[0] == "copy":
            text = " ".join(args[1:])
            if not text:
                text = (stdio.read_stdin() if stdio else None) or (sys.stdin.read() if not sys.stdin.isatty() else "")
            with open(clip_file(), "w", encoding="utf-8") as f:
                f.write(text)
            remember(text)
            console.print(f"[green]Copied {len(text)} character(s).[/green]")
        elif args[0] == "paste":
            sys.stdout.write(read_clip())
        elif args[0] == "list":
            show_list()
        elif args[0] in ("get", "show") and len(args) > 1:
            items = names()
            name = pick(items, args[1])
            if name:
                sys.stdout.write(read(name) if args[0] == "get" else "")
                if args[0] == "show":
                    show(name)
            else:
                console.print(f"[red]No snippet called '{escape(args[1])}'.[/red]")
        else:
            console.print("snippets [copy <text> | paste | list | get <name> | show <name>]  (no arguments opens the app)")
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
