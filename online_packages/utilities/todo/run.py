#!/usr/bin/env python3
import json
import os
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

console = Console()


def data_file():
    """Per-user storage inside the PyOS home directory (falls back to files/)."""
    try:
        with open("current_user.json") as f:
            user = json.load(f)["username"]
    except Exception:
        user = None
    folder = os.path.join("files", "home", user) if user else "files"
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, ".todo.json")


def load():
    try:
        with open(data_file()) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save(items):
    with open(data_file(), "w") as f:
        json.dump(items, f, indent=2)


def show(items):
    if not items:
        console.print("[yellow]Nothing to do. Add something with 'a'.[/yellow]")
        return
    table = Table(header_style="bold blue")
    table.add_column("#", justify="right")
    table.add_column("Done")
    table.add_column("Task")
    for i, item in enumerate(items, 1):
        table.add_row(str(i), "[green]x[/green]" if item["done"] else "", f"[dim]{item['text']}[/dim]" if item["done"] else item["text"])
    console.print(table)


def cli(args):
    """todo add <text> | list | done <n> | remove <n>"""
    items = load()
    sub = args[0].lower()
    if sub == "add" and len(args) > 1:
        items.append({"text": " ".join(args[1:]), "done": False})
        save(items)
        console.print(f"[green]Added #{len(items)}.[/green]")
    elif sub in ("list", "ls"):
        show(items)
    elif sub in ("done", "remove", "rm") and len(args) > 1 and args[1].isdigit() and 1 <= int(args[1]) <= len(items):
        n = int(args[1]) - 1
        if sub == "done":
            items[n]["done"] = not items[n]["done"]
        else:
            items.pop(n)
        save(items)
        show(items)
    else:
        console.print("todo [add <text> | list | done <n> | remove <n>]   (no arguments opens the list)")


def main():
    items = load()
    while True:
        console.print("\n[bold]To-do list[/bold]")
        show(items)
        action = Prompt.ask("(a)dd  (d)one  (e)dit  (r)emove  (c)lear finished  (q)uit", choices=["a", "d", "e", "r", "c", "q"], default="q")
        if action == "q":
            break
        if action == "a":
            text = Prompt.ask("Task").strip()
            if text:
                items.append({"text": text, "done": False})
        elif action == "c":
            items = [i for i in items if not i["done"]]
        elif items:
            num = Prompt.ask("Number")
            if num.isdigit() and 1 <= int(num) <= len(items):
                if action == "d":
                    items[int(num) - 1]["done"] = not items[int(num) - 1]["done"]
                elif action == "e":
                    text = Prompt.ask("New text", default=items[int(num) - 1]["text"]).strip()
                    if text:
                        items[int(num) - 1]["text"] = text
                else:
                    items.pop(int(num) - 1)
            else:
                console.print("[red]No such task.[/red]")
        save(items)


if __name__ == "__main__":
    main()


def execute(args=None):
    if args:
        cli(list(args))
    else:
        main()
