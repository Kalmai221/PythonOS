#!/usr/bin/env python3
"""Countdown: how many days until the things you are looking forward to.

    countdown                               everything, soonest first
    countdown add "Holiday" 2026-12-20      a date (YYYY-MM-DD), or: in 30 days, in 6 weeks
    countdown remove 2                      remove the second one in the list
    countdown past                          show events that already happened
"""
import datetime
import json
import os
import re
import sys

from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()


def data_file(name):
    """Per-user storage inside the PyOS home directory (falls back to files/)."""
    try:
        with open("current_user.json") as f:
            user = json.load(f)["username"]
    except Exception:
        user = None
    folder = os.path.join("files", "home", user) if user else "files"
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, name)


def load():
    try:
        with open(data_file(".countdown.json"), encoding="utf-8") as f:
            data = json.load(f)
        return [e for e in data if isinstance(e, dict) and "name" in e and "date" in e] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save(events):
    with open(data_file(".countdown.json"), "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, ensure_ascii=False)


def parse_date(text, today=None):
    """'2026-12-20', 'in 30 days', 'in 6 weeks', 'tomorrow' -> date. Raises ValueError."""
    today = today or datetime.date.today()
    text = text.strip().lower()
    if text == "today":
        return today
    if text == "tomorrow":
        return today + datetime.timedelta(days=1)
    m = re.fullmatch(r"in\s+(\d+)\s*(day|days|week|weeks|month|months|year|years)", text)
    if m:
        n, unit = int(m.group(1)), m.group(2).rstrip("s")
        if unit == "day":
            return today + datetime.timedelta(days=n)
        if unit == "week":
            return today + datetime.timedelta(weeks=n)
        months = n if unit == "month" else n * 12
        total = today.year * 12 + today.month - 1 + months
        year, month = divmod(total, 12)
        day = min(today.day, [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month])
        return datetime.date(year, month + 1, day)
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"'{text}' is not a date - try 2026-12-20, tomorrow or in 30 days") from None


def days_left(date_text, today=None):
    return (datetime.date.fromisoformat(date_text) - (today or datetime.date.today())).days


def describe(days):
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    if days == -1:
        return "yesterday"
    if days > 0:
        weeks, rest = divmod(days, 7)
        return f"in {days} days" + (f" ({weeks} week{'s' if weeks != 1 else ''}" + (f" {rest} day{'s' if rest != 1 else ''}" if rest else "") + ")" if weeks else "")
    return f"{-days} days ago"


def ordered(events, today=None, past=False):
    items = [e for e in events if (days_left(e["date"], today) < 0) == past]
    return sorted(items, key=lambda e: e["date"], reverse=past)


def main(args):
    events = load()
    command = args[0].lower() if args else "list"
    if command == "add":
        if len(args) < 3:
            console.print('[red]Usage:[/red] countdown add "Name" 2026-12-20   (or: in 30 days)')
            return 1
        try:
            date = parse_date(" ".join(args[2:]))
        except ValueError as e:
            console.print(f"[red]{escape(str(e))}[/red]")
            return 1
        events.append({"name": args[1], "date": date.isoformat()})
        save(events)
        console.print(f"[green]Added {escape(args[1])}: {describe(days_left(date.isoformat()))}.[/green]")
        return 0
    if command in ("remove", "rm"):
        shown = ordered(events)
        try:
            gone = shown[int(args[1]) - 1]
        except (IndexError, ValueError):
            console.print("[red]Say which one, by its number in the list.[/red]")
            return 1
        events.remove(gone)
        save(events)
        console.print(f"[green]Removed {escape(gone['name'])}.[/green]")
        return 0
    if command in ("list", "past"):
        shown = ordered(events, past=command == "past")
        if not shown:
            console.print("Nothing here yet. Add one: countdown add \"Holiday\" 2026-12-20")
            return 0
        table = Table(header_style="bold blue")
        for col in ("#", "Event", "Date", "When"):
            table.add_column(col)
        for i, e in enumerate(shown, 1):
            d = days_left(e["date"])
            table.add_row(str(i), escape(e["name"]), e["date"], f"[{'yellow' if 0 <= d <= 7 else 'dim' if d < 0 else 'green'}]{describe(d)}[/]")
        console.print(table)
        return 0
    console.print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
