#!/usr/bin/env python3
"""Habits: tick off what you did today and keep your streaks going.

    habits                       today's list (type a number to tick it), add and remove habits
    habits done <name>           tick a habit for today
    habits stats                 streaks and the last 7 days
"""
import datetime
import json
import os
import sys

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
    return os.path.join(folder, ".habits.json")


def load():
    try:
        with open(data_file()) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(habits):
    with open(data_file(), "w") as f:
        json.dump(habits, f, indent=2)


def today():
    return datetime.date.today()


def toggle(days, on=None):
    """Tick or untick a day in a habit's list of dates. Returns True when it is now ticked."""
    key = (on or today()).isoformat()
    if key in days:
        days.remove(key)
        return False
    days.append(key)
    days.sort()
    return True


def streak(days, on=None):
    """Days in a row up to today (or up to yesterday when today is not ticked yet, so a streak is not lost until the day ends)."""
    on = on or today()
    have = set(days)
    day = on if on.isoformat() in have else on - datetime.timedelta(days=1)
    count = 0
    while day.isoformat() in have:
        count += 1
        day -= datetime.timedelta(days=1)
    return count


def best_streak(days):
    best = run = 0
    previous = None
    for text in sorted(set(days)):
        day = datetime.date.fromisoformat(text)
        run = run + 1 if previous and (day - previous).days == 1 else 1
        best = max(best, run)
        previous = day
    return best


def week(days, on=None):
    on = on or today()
    return "".join("[green]#[/green]" if (on - datetime.timedelta(days=back)).isoformat() in days else "[dim].[/dim]" for back in range(6, -1, -1))


def show(habits, stats=False):
    if not habits:
        console.print("[yellow]No habits yet. Add one with 'a'.[/yellow]")
        return
    table = Table(header_style="bold blue")
    columns = ("#", "Habit", "Today", "Streak", "Last 7 days") + (("Best",) if stats else ())
    for column in columns:
        table.add_column(column, justify="right" if column in ("#", "Streak", "Best") else "left")
    key = today().isoformat()
    for number, (name, days) in enumerate(sorted(habits.items()), 1):
        row = [str(number), name, "[green]done[/green]" if key in days else "", str(streak(days)), week(days)]
        table.add_row(*row, *([str(best_streak(days))] if stats else []))
    console.print(table)


def menu():
    habits = load()
    while True:
        console.print("\n[bold]Habits[/bold]  [dim]" + today().strftime("%A %d %B") + "[/dim]")
        show(habits)
        action = Prompt.ask("(t)ick or untick  (a)dd  (r)emove  (s)tats  (q)uit", choices=["t", "a", "r", "s", "q"], default="q")
        names = sorted(habits)
        if action == "q":
            break
        if action == "a":
            name = Prompt.ask("Habit").strip()
            if name and name not in habits:
                habits[name] = []
        elif action == "s":
            show(habits, stats=True)
        elif names:
            number = Prompt.ask("Number")
            if number.isdigit() and 1 <= int(number) <= len(names):
                name = names[int(number) - 1]
                if action == "t":
                    toggle(habits[name])
                else:
                    del habits[name]
        save(habits)


def execute(args=None):
    try:
        args = list(args or [])
        if args[:1] == ["done"] and len(args) > 1:
            habits = load()
            name = " ".join(args[1:])
            if name not in habits:
                console.print(f"[red]No habit called {name}.[/red]")
                return False
            if key_in(habits[name]):
                console.print("[dim]Already ticked today.[/dim]")
            else:
                toggle(habits[name])
                save(habits)
                console.print(f"[green]{name}: {streak(habits[name])} day(s) in a row.[/green]")
        elif args[:1] == ["stats"]:
            show(load(), stats=True)
        else:
            menu()
    except (KeyboardInterrupt, EOFError):
        console.print()
    return True


def key_in(days):
    return today().isoformat() in days


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
