#!/usr/bin/env python3
"""Journal: a private diary in your home folder.

    journal                         write today's entry (an empty line ends it)
    journal add It rained all day   add a line to today without the prompt
    journal list                    the days you wrote, newest first
    journal show 2026-10-06         read a day (or: today, yesterday)
    journal search garden           every entry containing a word
"""
import datetime
import json
import os
import sys

from rich.console import Console
from rich.markup import escape

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
        with open(data_file(".journal.json"), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data):
    with open(data_file(".journal.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_entry(data, text, now=None):
    now = now or datetime.datetime.now()
    day = data.setdefault(now.strftime("%Y-%m-%d"), [])
    day.append({"time": now.strftime("%H:%M"), "text": text.strip()})
    return day[-1]


def resolve_day(word, today=None):
    today = today or datetime.date.today()
    word = word.lower()
    if word == "today":
        return today.isoformat()
    if word == "yesterday":
        return (today - datetime.timedelta(days=1)).isoformat()
    try:
        return datetime.date.fromisoformat(word).isoformat()
    except ValueError:
        return None


def search(data, word):
    """[(day, time, text)] of the entries containing `word`, newest first."""
    word = word.lower()
    found = [(day, e["time"], e["text"]) for day, entries in data.items() for e in entries if word in e["text"].lower()]
    return sorted(found, reverse=True)


def show_day(day, entries):
    console.print(f"[bold]{day}[/bold]  [dim]{datetime.date.fromisoformat(day).strftime('%A')}[/dim]")
    for entry in entries:
        console.print(f"  [dim]{entry['time']}[/dim]  {escape(entry['text'])}")


def execute(args=None):
    args = list(args or [])
    data = load()
    try:
        if not args:
            console.print("[dim]Write your entry. An empty line ends it.[/dim]")
            lines = []
            while True:
                line = input("> ")
                if not line.strip():
                    break
                lines.append(line.strip())
            if lines:
                add_entry(data, " ".join(lines))
                save(data)
                console.print("[green]Saved.[/green]")
            return True
        sub, rest = args[0].lower(), args[1:]
        if sub == "add" and rest:
            add_entry(data, " ".join(rest))
            save(data)
            console.print("[green]Saved.[/green]")
        elif sub == "list":
            if not data:
                console.print("[yellow]Nothing written yet. Start with: journal[/yellow]")
            for day in sorted(data, reverse=True):
                console.print(f"{day}  [dim]{len(data[day])} entr{'y' if len(data[day]) == 1 else 'ies'}[/dim]")
        elif sub == "show" and rest:
            day = resolve_day(rest[0])
            if day is None or day not in data:
                console.print("[yellow]No entry for that day. journal list shows the days you wrote.[/yellow]")
                return False
            show_day(day, data[day])
        elif sub == "search" and rest:
            found = search(data, " ".join(rest))
            for day, time_, text in found[:30]:
                console.print(f"[bold]{day}[/bold] [dim]{time_}[/dim]  {escape(text[:120])}")
            if not found:
                console.print("[yellow]Nothing found.[/yellow]")
        else:
            console.print("[bold red]Usage:[/bold red] journal [add <text> | list | show <date> | search <word>]")
            return False
    except (KeyboardInterrupt, EOFError):
        console.print()
    return True


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
