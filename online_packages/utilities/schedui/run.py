#!/usr/bin/env python3
"""Scheduler: a friendly way to run commands later or repeatedly - once after a delay, at a time of day, every few minutes or daily.
Add tasks with a short guided form, see when each runs next, run one now, and remove it. Results arrive as notifications. Tasks run
while you are logged in and cannot ask questions. This is a front end for the shell's `schedule` command.
Usage: schedui  (menu)  |  schedui list"""
import datetime
import os
import sys

from rich.console import Console
from rich.markup import escape
from rich.prompt import IntPrompt, Prompt
from rich.table import Table

import pyos
from pyos import scheduler

console = Console()
PRESETS = [
    ("Back up my files every day at 02:00", ["daily", "02:00", "backup", "create"]),
    ("Say good morning at 08:00", ["daily", "08:00", "echo", "Good morning!"]),
    ("Show disk space every hour", ["every", "1h", "df"]),
    ("Remind me to stretch every 45 minutes", ["every", "45m", "echo", "Time to stand up and stretch!"]),
]


def user():
    return pyos.userinfo()[0]


def known_commands():
    try:
        return {f[:-3] for f in os.listdir("commands") if f.endswith(".py")} | {"echo", "run"}
    except OSError:
        return {"echo", "run"}


def show():
    tasks = scheduler.tasks_for(user())
    if not tasks:
        console.print("[dim]Nothing scheduled yet. Choose (a)dd to make something happen on its own.[/dim]")
        return tasks
    table = Table(header_style="bold blue", title="Scheduled tasks")
    for col in ("#", "When", "Next run", "In", "Command", "Last"):
        table.add_column(col)
    now = datetime.datetime.now()
    for t in tasks:
        nxt = datetime.datetime.fromtimestamp(t["next_run"])
        delta = nxt - now
        minutes = int(delta.total_seconds() // 60)
        until = "now" if minutes <= 0 else f"{minutes} min" if minutes < 120 else f"{minutes // 60} h {minutes % 60} min" if minutes < 2880 else f"{minutes // 1440} days"
        last = "-" if t["last_run"] is None else ("[green]ok[/green]" if not t["last_status"] else "[red]failed[/red]")
        table.add_row(str(t["id"]), scheduler.describe(t), nxt.strftime("%a %d %b %H:%M"), until, escape(t["command"]), last)
    console.print(table)
    return tasks


def guided_add():
    console.print("When should it run?\n  [cyan]1[/cyan] once, after a delay (like in 10 minutes)\n  [cyan]2[/cyan] once, at a time today or tomorrow\n"
                  "  [cyan]3[/cyan] over and over, every so often\n  [cyan]4[/cyan] every day at a time\n  [cyan]5[/cyan] pick a ready-made example")
    kind = Prompt.ask("Choose", choices=["1", "2", "3", "4", "5"], default="1")
    if kind == "5":
        for i, (label, _) in enumerate(PRESETS, 1):
            console.print(f"  [cyan]{i}[/cyan] {label}")
        n = IntPrompt.ask("Number", default=1)
        if not 1 <= n <= len(PRESETS):
            return
        words = PRESETS[n - 1][1]
    else:
        if kind == "1":
            when = ["in", Prompt.ask("How long? (like 30s, 10m, 2h, 1d)")]
        elif kind == "2":
            when = ["at", Prompt.ask("What time? (HH:MM, 24-hour)")]
        elif kind == "3":
            when = ["every", Prompt.ask("How often? (like 5m, 1h)")]
        else:
            when = ["daily", Prompt.ask("What time? (HH:MM, 24-hour)")]
        command = Prompt.ask("What should it do? (a command, like  echo hello  or  backup create)").strip()
        if not command or command.split()[0] not in known_commands():
            console.print("[red]I do not know that command (see: help).[/red]")
            return
        words = when + command.split()
    try:
        task = scheduler.add(user(), words)
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        return
    console.print(f"[green]Scheduled #{task['id']}: {escape(task['command'])} ({scheduler.describe(task)})[/green]")


def run_now(task_id):
    """Ask the scheduler to run a copy of the task in a second; the answer arrives as a notification."""
    task = next((t for t in scheduler.tasks_for(user()) if t["id"] == task_id), None)
    if not task:
        console.print("[red]No such task.[/red]")
        return
    try:
        scheduler.add(user(), ["in", "1s"] + task["command"].split())
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        return
    console.print("[green]Running it now.[/green] The result will arrive as a notification in a moment (see: notifications).")


def main(args):
    if args and args[0] == "list":
        show()
        return
    while True:
        tasks = show()
        choice = Prompt.ask("(a)dd, (r)emove, run (n)ow, (q)uit", choices=["a", "r", "n", "q"], default="q")
        if choice == "q":
            return
        if choice == "a":
            guided_add()
        elif tasks:
            n = IntPrompt.ask("Task number")
            if choice == "r":
                console.print("[green]Removed.[/green]" if scheduler.remove(user(), n) else "[red]No such task.[/red]")
            else:
                run_now(n)


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
