#!/usr/bin/env python3
"""Process and jobs inspector: see what is running - PythonOS's background jobs and the programs (processes) on this computer - and look
closer at one: its memory, CPU, how long it has been running, what it has open. On a locked-down system only PythonOS's own processes are
shown. You can stop a process you started (with confirmation).
Commands: p (processes), j (jobs), N (details of process N), k N (stop process N), s cpu|mem|name (sort), f WORD (filter), r (refresh), q."""
import json
import os
import sys
import time

import psutil
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

console = Console()
try:
    from pyos import lockdown
    LOCKED = lockdown.enabled
except ImportError:
    LOCKED = lambda: False  # noqa: E731


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def duration(seconds):
    seconds = int(seconds)
    d, rest = divmod(seconds, 86400)
    h, rest = divmod(rest, 3600)
    m, s = divmod(rest, 60)
    return (f"{d}d " if d else "") + (f"{h}h " if h or d else "") + f"{m}m {s}s"


def processes():
    """[(pid, name, cpu %, memory %, started)] for the processes this account may see (PythonOS's own tree when locked down)."""
    if LOCKED():
        try:
            me = psutil.Process(os.getpid())
            pool = [me] + me.parents()[:1] + me.children(recursive=True)
        except psutil.Error:
            pool = []
    else:
        pool = psutil.process_iter()
    rows = []
    for p in pool:
        try:
            with p.oneshot():
                rows.append({"pid": p.pid, "name": p.name(), "cpu": p.cpu_percent(None), "mem": p.memory_percent(), "rss": p.memory_info().rss,
                             "started": p.create_time(), "user": ""})
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return rows


def read_jobs():
    try:
        with open(os.path.join(".OSData", "jobs.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def show_processes(rows, sort="mem", word=None, limit=25):
    if word:
        rows = [r for r in rows if word.lower() in r["name"].lower()]
    key = {"cpu": lambda r: -r["cpu"], "mem": lambda r: -r["mem"], "name": lambda r: r["name"].lower()}[sort]
    rows = sorted(rows, key=key)
    table = Table(title=f"Processes ({len(rows)}){' - PythonOS only' if LOCKED() else ''}", header_style="bold blue")
    table.add_column("#", justify="right", style="dim")
    table.add_column("PID", justify="right")
    table.add_column("Name")
    table.add_column("CPU %", justify="right")
    table.add_column("Memory", justify="right")
    table.add_column("Running for", justify="right")
    for i, r in enumerate(rows[:limit], 1):
        table.add_row(str(i), str(r["pid"]), escape(r["name"]), f"{r['cpu']:.1f}", human(r["rss"]), duration(time.time() - r["started"]))
    console.print(table)
    return rows[:limit]


def show_jobs():
    jobs = read_jobs()
    if not jobs:
        console.print("[dim]No background jobs. Start one with a command that ends in &, for example:  sleep 30 &[/dim]")
        return
    table = Table(title="Background jobs", header_style="bold blue")
    for col in ("#", "State", "Time", "Command"):
        table.add_column(col)
    for j in jobs:
        colour = {"running": "yellow", "done": "green", "failed": "red", "cancelled": "dim"}.get(j["status"], "white")
        table.add_row(str(j["id"]), f"[{colour}]{j['status']}[/{colour}]", duration(j["elapsed"]), escape(j["command"]))
    console.print(table)
    console.print("[dim]Manage jobs with the shell: jobs, fg N, kill N.[/dim]")


def details(pid):
    try:
        p = psutil.Process(pid)
        with p.oneshot():
            lines = [f"[bold]{escape(p.name())}[/bold]  PID {pid}", f"Status: {p.status()}", f"Memory: {human(p.memory_info().rss)} ({p.memory_percent():.1f}%)",
                     f"CPU: {p.cpu_percent(0.2):.1f}%  threads: {p.num_threads()}", f"Running for: {duration(time.time() - p.create_time())}"]
            try:
                lines.append("Command: " + escape(" ".join(p.cmdline())[:200]))
            except (psutil.AccessDenied, psutil.ZombieProcess):
                pass
            try:
                files = p.open_files()
                lines.append(f"Open files: {len(files)}" + ("".join(f"\n  {escape(f.path[-80:])}" for f in files[:5]) if files else ""))
                lines.append(f"Network connections: {len(p.net_connections()) if hasattr(p, 'net_connections') else len(p.connections())}")
            except (psutil.AccessDenied, psutil.ZombieProcess, AttributeError):
                pass
        console.print(Panel("\n".join(lines), border_style="blue", expand=False))
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        console.print(f"[red]Cannot look at that process: {escape(str(e))}[/red]")


def stop(pid):
    if pid == os.getpid() or pid == os.getppid():
        console.print("[red]That would stop PythonOS itself.[/red]")
        return
    try:
        p = psutil.Process(pid)
        if not Confirm.ask(f"Stop {escape(p.name())} (PID {pid})?", default=False):
            return
        p.terminate()
        try:
            p.wait(3)
            console.print("[green]Stopped.[/green]")
        except psutil.TimeoutExpired:
            if Confirm.ask("It did not stop. Force it to end?", default=False):
                p.kill()
                console.print("[green]Ended.[/green]")
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        console.print(f"[red]Not allowed or already gone: {escape(str(e))}[/red]")


def main(args):
    sort, word, shown = "mem", None, []
    for p in psutil.process_iter():                      # warm up the CPU counters
        try:
            p.cpu_percent(None)
        except psutil.Error:
            pass
    time.sleep(0.3)
    shown = show_processes(processes(), sort, word)
    while True:
        try:
            parts = input("procs> ").strip().split(None, 1)
        except EOFError:
            return
        if not parts:
            continue
        cmd, rest = parts[0].lower(), parts[1].strip() if len(parts) > 1 else ""
        if cmd in ("q", "quit"):
            return
        if cmd in ("p", "r"):
            shown = show_processes(processes(), sort, word)
        elif cmd == "j":
            show_jobs()
        elif cmd == "s" and rest in ("cpu", "mem", "name"):
            sort = rest
            shown = show_processes(processes(), sort, word)
        elif cmd == "f":
            word = rest or None
            shown = show_processes(processes(), sort, word)
        elif cmd == "k" and rest.isdigit() and 1 <= int(rest) <= len(shown):
            stop(shown[int(rest) - 1]["pid"])
        elif cmd.isdigit() and 1 <= int(cmd) <= len(shown):
            details(shown[int(cmd) - 1]["pid"])
        else:
            console.print("[yellow]p processes, j jobs, N details, k N stop, s cpu|mem|name, f WORD filter, r refresh, q quit[/yellow]")


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
