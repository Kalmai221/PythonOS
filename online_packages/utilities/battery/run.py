#!/usr/bin/env python3
"""Battery and power: charge level, whether you are plugged in, estimated time left, and (where the device reports them) temperature and
fan speed. 'battery log' records readings over time so you can see how fast the battery drains.
Usage: battery  |  battery watch  |  battery log  |  battery history"""
import sys
import time

import psutil
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()


def human_time(seconds):
    if seconds in (psutil.POWER_TIME_UNKNOWN, psutil.POWER_TIME_UNLIMITED) or seconds is None or seconds < 0:
        return "unknown"
    h, rest = divmod(int(seconds), 3600)
    return f"{h} h {rest // 60} min" if h else f"{rest // 60} min"


def reading():
    """Current battery state as a dict, or None if this device has no battery."""
    try:
        b = psutil.sensors_battery()
    except (AttributeError, NotImplementedError, OSError):
        return None
    if b is None:
        return None
    return {"percent": round(b.percent, 1), "plugged": bool(b.power_plugged), "left": b.secsleft, "time": time.time()}


def temperatures():
    try:
        data = psutil.sensors_temperatures()
    except (AttributeError, NotImplementedError, OSError):
        return {}
    return {name: [t.current for t in entries if t.current] for name, entries in (data or {}).items() if entries}


def fans():
    try:
        data = psutil.sensors_fans()
    except (AttributeError, NotImplementedError, OSError):
        return {}
    return {name: [f.current for f in entries] for name, entries in (data or {}).items() if entries}


def bar(percent, width=30):
    filled = int(width * percent / 100)
    colour = "green" if percent >= 50 else "yellow" if percent >= 20 else "red"
    return f"[{colour}]" + "#" * filled + f"[/{colour}][dim]" + "-" * (width - filled) + "[/dim]"


def panel(r):
    state = "charging / plugged in" if r["plugged"] else "on battery"
    table = Table(show_header=False, box=None)
    table.add_row("Charge", f"{bar(r['percent'])} [bold]{r['percent']:.0f}%[/bold]")
    table.add_row("Power", state)
    table.add_row("Time left" if not r["plugged"] else "Charging", human_time(r["left"]) if not r["plugged"] else ("full" if r["percent"] >= 99 else "in progress"))
    temps = temperatures()
    if temps:
        name, values = next(iter(temps.items()))
        table.add_row("Temperature", f"{max(values):.0f} C ({name})")
    speeds = fans()
    if speeds:
        name, values = next(iter(speeds.items()))
        table.add_row("Fan", f"{values[0]} rpm")
    return Panel(table, title="Battery", border_style="green" if r["percent"] >= 20 else "red", expand=False)


def log_reading(r):
    if appdata:
        history = appdata.load("battery", [])
        history.append({"t": int(r["time"]), "p": r["percent"], "plugged": r["plugged"]})
        appdata.save("battery", history[-500:])


def history():
    rows = appdata.load("battery", []) if appdata else []
    if len(rows) < 2:
        console.print("[dim]Not enough readings yet. Run 'battery log' now and then (or 'battery watch').[/dim]")
        return
    table = Table(header_style="bold blue", title="Battery history")
    for col in ("When", "Charge", "Power"):
        table.add_column(col)
    for row in rows[-20:]:
        table.add_row(time.strftime("%Y-%m-%d %H:%M", time.localtime(row["t"])), f"{row['p']:.0f}%", "plugged in" if row["plugged"] else "battery")
    console.print(table)
    discharging = [(a, b) for a, b in zip(rows, rows[1:]) if not a["plugged"] and not b["plugged"] and b["t"] > a["t"] and b["p"] < a["p"]]
    if discharging:
        drop = sum(a["p"] - b["p"] for a, b in discharging)
        hours = sum(b["t"] - a["t"] for a, b in discharging) / 3600
        if hours > 0:
            console.print(f"[dim]On battery it drains about {drop / hours:.1f}% per hour (a full charge would last about {100 / (drop / hours):.1f} hours).[/dim]")


def main(args):
    r = reading()
    if r is None:
        console.print("[yellow]This device has no battery (or does not report one).[/yellow]")
        return
    cmd = args[0] if args else "show"
    if cmd == "history":
        history()
    elif cmd == "log":
        log_reading(r)
        console.print(panel(r))
        console.print("[dim]Reading saved.[/dim]")
    elif cmd == "watch":
        try:
            with Live(panel(r), console=console, refresh_per_second=1) as live:
                last_log = 0
                while True:
                    r = reading() or r
                    live.update(panel(r))
                    if time.time() - last_log > 60:
                        log_reading(r)
                        last_log = time.time()
                    time.sleep(2)
        except KeyboardInterrupt:
            console.print()
    else:
        console.print(panel(r))
        if r["percent"] < 20 and not r["plugged"]:
            console.print("[bold red]Battery is low - plug in soon.[/bold red]")


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
