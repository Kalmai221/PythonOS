#!/usr/bin/env python3
"""Startup apps: choose commands that PythonOS runs for you every time you log in - a greeting, a backup, a status check, opening a
program's report. They run in the background right after login and any output arrives as a notification. They cannot ask questions.
Usage: startup  (menu)  |  startup list  |  startup add <command...>  |  startup remove N  |  startup on N  |  startup off N  |  startup test N"""
import os
import sys

from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from pyos import appdata, startup

console = Console()
INTERACTIVE = {"edit", "nano", "su", "passwd", "lock", "manageusers", "tutorial", "shutdown", "restart", "wipe", "logout", "exit", "fg",
               "hwsetup", "persist", "settings"}


def known_commands():
    """Names of the commands that exist (the files in commands/) plus the shell's own words."""
    try:
        names = {f[:-3] for f in os.listdir("commands") if f.endswith(".py")}
    except OSError:
        names = set()
    return names | {"run", "echo", "help", "reload"}


def load():
    return list(startup.items())


def save(items):
    appdata.save("startup", {"items": items[:startup.MAX_ITEMS]})


def check_command(command):
    """Returns an error message, or None if the command is acceptable as a startup item."""
    words = command.strip().split()
    if not words:
        return "Type a command."
    if len(command) > 200:
        return "That command is too long."
    if words[0] in INTERACTIVE:
        return f"'{words[0]}' needs you to answer questions, so it cannot run on its own."
    if words[0] not in known_commands():
        return f"I do not know a command called '{words[0]}' (see: help)."
    return None


def show(items):
    if not items:
        console.print("[dim]No startup commands yet. Add one with:  startup add date[/dim]")
        return
    table = Table(header_style="bold blue", title="Runs at login")
    for col in ("#", "Command", "State"):
        table.add_column(col)
    for i, item in enumerate(items, 1):
        table.add_row(str(i), escape(item["command"]), "[green]on[/green]" if item.get("enabled", True) else "[dim]off[/dim]")
    console.print(table)


def run_test(item):
    """Run a copy of the command in a second through the scheduler; the output arrives as a notification."""
    from pyos import scheduler
    try:
        scheduler.add(startup_user(), ["in", "1s"] + item["command"].split())
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        return
    console.print("[green]Testing it now.[/green] What it says arrives as a notification in a moment (see: notifications).")


def startup_user():
    import pyos
    return pyos.userinfo()[0]


def pick(items, text):
    if text.isdigit() and 1 <= int(text) <= len(items):
        return int(text) - 1
    return None


def act(items, cmd, rest):
    """Handle one command; returns a message to print (or None)."""
    if cmd == "list":
        return None
    if cmd == "add":
        error = check_command(rest)
        if error:
            return f"[red]{escape(error)}[/red]"
        if len(items) >= startup.MAX_ITEMS:
            return f"[red]You can have at most {startup.MAX_ITEMS} startup commands.[/red]"
        items.append({"command": rest.strip(), "enabled": True})
        save(items)
        return f"[green]Added. It will run at your next login.[/green]"
    i = pick(items, rest.strip())
    if cmd in ("remove", "rm", "delete", "on", "off", "test") and i is None:
        return "[red]Give the number from the list.[/red]"
    if cmd in ("remove", "rm", "delete"):
        removed = items.pop(i)
        save(items)
        return f"[green]Removed {escape(removed['command'])}.[/green]"
    if cmd in ("on", "off"):
        items[i]["enabled"] = cmd == "on"
        save(items)
        return f"[green]{'Enabled' if cmd == 'on' else 'Disabled'}.[/green]"
    if cmd == "test":
        run_test(items[i])
        return None
    return "[yellow]startup [list | add <command> | remove N | on N | off N | test N][/yellow]"


def main(args):
    items = load()
    if args:
        message = act(items, args[0].lower(), " ".join(args[1:]))
        if message:
            console.print(message)
        show(load())
        return
    while True:
        show(items)
        choice = Prompt.ask("(a)dd, (r)emove, (t)oggle on/off, t(e)st, (q)uit", choices=["a", "r", "t", "e", "q"], default="q")
        if choice == "q":
            return
        if choice == "a":
            message = act(items, "add", Prompt.ask("Command to run at login"))
        else:
            if not items:
                continue
            n = str(IntPrompt.ask("Number"))
            if choice == "r":
                message = act(items, "remove", n)
            elif choice == "t":
                i = pick(items, n)
                message = act(items, "off" if i is not None and items[i].get("enabled", True) else "on", n)
            else:
                message = act(items, "test", n)
        if message:
            console.print(message)
        items = load()


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
