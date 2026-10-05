#!/usr/bin/env python3
"""Clipboard history: everything you copied with the Snippets app (or  snippets copy ... ) is remembered here, newest first. Search it, view
an entry in full, copy an old entry back to the clipboard, pin the ones you always need, and clear the list. Pinned entries are never pushed
out by new copies. Usage: clipboard  (menu)  |  clipboard list  |  clipboard get N  |  clipboard clear"""
import os
import sys
import time

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from pyos import appdata, fs

console = Console()
MAX = 50


def history():
    return appdata.load("clip_history", []) or []


def pins():
    return appdata.load("clip_pins", []) or []


def entries():
    """Pinned entries first, then the history (no duplicates): [{text, t, pinned}]."""
    pinned = [{"text": t, "t": 0, "pinned": True} for t in pins()]
    seen = set(pins())
    return pinned + [dict(h, pinned=False) for h in history() if h.get("text") not in seen]


def clip_file():
    name = fs.current_user()[0]
    base = fs.home_dir(name) if name else fs.BASE_DIR
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, ".clipboard")


def show(rows, term=None):
    if term:
        rows = [r for r in rows if term.lower() in r["text"].lower()]
    if not rows:
        console.print("[dim]Nothing here yet. Copy something with the Snippets app (snippets copy hello).[/dim]")
        return rows
    table = Table(header_style="bold blue", title="Clipboard history" + (f" matching '{term}'" if term else ""))
    table.add_column("#", justify="right")
    table.add_column("", width=2)
    table.add_column("Copied", style="dim")
    table.add_column("Text")
    for i, r in enumerate(rows[:MAX], 1):
        first = r["text"].strip().splitlines()[0] if r["text"].strip() else ""
        table.add_row(str(i), "*" if r["pinned"] else "", time.strftime("%d %b %H:%M", time.localtime(r["t"])) if r["t"] else "pinned",
                      escape(first[:70]) + (" ..." if len(first) > 70 or "\n" in r["text"].strip() else ""))
    console.print(table)
    return rows


def copy_back(text):
    with open(clip_file(), "w", encoding="utf-8") as f:
        f.write(text)
    h = [x for x in history() if x.get("text") != text]
    h.insert(0, {"t": int(time.time()), "text": text})
    appdata.save("clip_history", h[:MAX])
    console.print("[green]Copied back to the clipboard.[/green]")


def main(args):
    rows = entries()
    if args and args[0] == "list":
        show(rows)
        return
    if args and args[0] == "get" and len(args) > 1 and args[1].isdigit() and 1 <= int(args[1]) <= len(rows):
        console.print(rows[int(args[1]) - 1]["text"], markup=False, highlight=False)
        return
    if args and args[0] == "clear":
        appdata.save("clip_history", [])
        console.print("[green]History cleared (pinned entries are kept).[/green]")
        return
    term = None
    while True:
        shown = show(rows, term)
        choice = Prompt.ask("Number to open, (s)earch, (c)lear history, (q)uit", default="q").strip().lower()
        if choice == "q":
            return
        if choice == "s":
            term = Prompt.ask("Search for", default="").strip() or None
        elif choice == "c":
            appdata.save("clip_history", [])
            rows, term = entries(), None
        elif choice.isdigit() and 1 <= int(choice) <= len(shown):
            row = shown[int(choice) - 1]
            console.print(Panel(escape(row["text"][:3000]), border_style="blue", title="Entry"))
            action = Prompt.ask("(c)opy back, (p)in/unpin, (d)elete, (b)ack", choices=["c", "p", "d", "b"], default="b")
            if action == "c":
                copy_back(row["text"])
            elif action == "p":
                p = pins()
                if row["pinned"]:
                    p.remove(row["text"])
                else:
                    p.append(row["text"])
                appdata.save("clip_pins", p[:20])
            elif action == "d":
                appdata.save("clip_history", [h for h in history() if h.get("text") != row["text"]])
                appdata.save("clip_pins", [t for t in pins() if t != row["text"]])
            rows = entries()


def execute(args=None):
    try:
        main(list(args or []))
    except (OSError, PermissionError) as e:
        console.print(f"[red]{escape(fs.errtext(e))}[/red]")
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
