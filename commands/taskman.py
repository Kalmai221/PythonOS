#!/usr/bin/env python3
"""Task manager: the tasks running inside PythonOS (the shell, services, jobs, the marketplace and whatever else is open)."""
import time

from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt
from rich.table import Table

import pyos
from pyos import resources, tasks

console = Console()

config = {
    "name": "taskman",
    "description": "Task manager: what is running in PythonOS, with CPU, memory and stop.",
    "alias": ["top"],
}

SORTS = {"cpu": ("cpu_percent", True), "mem": ("rss", True), "memory": ("rss", True), "pid": ("pid", False), "name": ("name", False),
         "time": ("cpu_time", True), "user": ("user", False)}
STATE_COLOUR = {"running": "green", "sleeping": "dim"}


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def clock(seconds):
    seconds = int(seconds)
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def show(rows, sort_by="pid", reverse=False, limit=25):
    total, used, available, percent = resources.snapshot()
    info = tasks.summary(rows)
    console.print(f"Tasks: {info['total']} total, [green]{info['running']} running[/green], {info['sleeping']} sleeping    "
                  f"Memory: {human(used)} used of {human(total)} ({percent:.0f}%)")
    table = Table(header_style="bold blue", box=None, pad_edge=False)
    for column, align in (("PID", "right"), ("PPID", "right"), ("USER", "left"), ("STATE", "left"), ("CPU%", "right"),
                          ("MEM", "right"), ("MEM%", "right"), ("TIME", "right"), ("TASK", "left")):
        table.add_column(column, justify=align)
    for row in sorted(rows, key=lambda r: r[sort_by] if r[sort_by] is not None else 0, reverse=reverse)[:limit]:
        colour = STATE_COLOUR.get(row["state"], "white")
        what = f"[bold]{escape(row['name'])}[/bold] [dim]{escape(row['cmd'])}[/dim]" if row["cmd"] != row["name"] else escape(row["name"])
        table.add_row(str(row["pid"]), str(row["ppid"]), escape(row["user"]), f"[{colour}]{row['state']}[/{colour}]",
                      f"{row['cpu_percent']:.1f}", human(row["rss"]), f"{row['memory_percent']:.1f}", clock(row["cpu_time"]), what)
    console.print(table)


def main():
    user, role = pyos.userinfo()[0], pyos.userinfo()[1]
    sort_by, reverse, limit = "pid", False, 25
    tasks.listing()                                    # first look: sets the starting point for the CPU figures
    time.sleep(1.0)
    while True:
        console.clear()
        console.print("[bold]Task Manager[/bold]\n")
        show(tasks.listing(), sort_by, reverse, limit)
        console.print("\n[b]kill <pid>[/b] stop a job or service   [b]sort <cpu|mem|pid|name|time|user>[/b]   [b]limit <n>[/b]   "
                      "[b]refresh[/b]   [b]quit[/b]\n")
        cmd = Prompt.ask("Enter command").strip().lower()
        parts = cmd.split()
        if not parts or parts[0] == "refresh":
            time.sleep(0.3)
            continue
        if parts[0] in ("quit", "q", "exit"):
            break
        if parts[0] == "kill":
            if len(parts) != 2 or not parts[1].isdigit():
                console.print("[red]Usage: kill <pid>[/red]")
            else:
                ok, message = tasks.stop(int(parts[1]), user, admin=(role == "admin"))
                colour = "green" if ok else "yellow"
                console.print(f"[{colour}]{escape(message)}[/{colour}]")
        elif parts[0] == "sort":
            if len(parts) == 2 and parts[1] in SORTS:
                sort_by, reverse = SORTS[parts[1]]
            else:
                console.print("[red]Use: sort cpu, mem, pid, name, time or user.[/red]")
        elif parts[0] == "limit":
            if len(parts) == 2 and parts[1].isdigit():
                limit = max(1, int(parts[1]))
            else:
                console.print("[red]Usage: limit <number>[/red]")
        else:
            console.print("[red]Unknown command.[/red]")
        console.print("\nPress Enter to continue...")
        input()


def execute():
    main()
