#!/usr/bin/env python3
import datetime
import json
import os
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

console = Console()


def notes_dir():
    """Notes live in ~/notes so they are ordinary files you can also cat, grep or edit."""
    try:
        with open("current_user.json") as f:
            user = json.load(f)["username"]
    except Exception:
        user = None
    folder = os.path.join("files", "home", user, "notes") if user else os.path.join("files", "notes")
    os.makedirs(folder, exist_ok=True)
    return folder


def note_files():
    return sorted(f for f in os.listdir(notes_dir()) if f.endswith(".txt"))


def list_notes():
    names = note_files()
    if not names:
        console.print("[yellow]No notes yet. Press 'n' to write one.[/yellow]")
        return names
    table = Table(header_style="bold blue")
    table.add_column("#", justify="right")
    table.add_column("Title")
    table.add_column("Modified", style="dim")
    for i, name in enumerate(names, 1):
        stamp = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(notes_dir(), name)))
        table.add_row(str(i), name[:-4], stamp.strftime("%Y-%m-%d %H:%M"))
    console.print(table)
    return names


def pick(names):
    num = Prompt.ask("Note number")
    if num.isdigit() and 1 <= int(num) <= len(names):
        return names[int(num) - 1]
    console.print("[red]No such note.[/red]")
    return None


def new_note():
    title = Prompt.ask("Title").strip()
    safe = "".join(c for c in title if c.isalnum() or c in " -_").strip()
    if not safe:
        console.print("[red]Please use letters or numbers in the title.[/red]")
        return
    console.print("Write your note. Finish with a line containing only [bold].[/bold]")
    lines = []
    while True:
        line = input()
        if line.strip() == ".":
            break
        lines.append(line)
    with open(os.path.join(notes_dir(), safe + ".txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    console.print("[green]Saved.[/green]")


def main():
    while True:
        console.print("\n[bold]Notes[/bold]")
        names = list_notes()
        action = Prompt.ask("[n]ew  [r]ead  [d]elete  [q]uit", choices=["n", "r", "d", "q"], default="q")
        if action == "q":
            break
        if action == "n":
            new_note()
        elif names:
            name = pick(names)
            if not name:
                continue
            path = os.path.join(notes_dir(), name)
            if action == "r":
                with open(path, encoding="utf-8") as f:
                    console.print(Panel(escape(f.read()), title=name[:-4], border_style="blue"))
            else:
                os.remove(path)
                console.print("[green]Deleted.[/green]")


if __name__ == "__main__":
    main()


def execute():
    main()
