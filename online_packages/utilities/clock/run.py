#!/usr/bin/env python3
"""Clock: the time, world clocks, a timer, a stopwatch and alarms in one app (like the phone Clock app)."""
import datetime
import re
import threading
import time

from rich.console import Console
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

try:
    from pyos import appdata, notify, scheduler
    import pyos
except ImportError:  # outside PythonOS: the app still works, alarms and notifications just are not available
    appdata = notify = scheduler = pyos = None

console = Console()
CITIES = {"London": "Europe/London", "New York": "America/New_York", "Los Angeles": "America/Los_Angeles",
          "Paris": "Europe/Paris", "Dubai": "Asia/Dubai", "Delhi": "Asia/Kolkata", "Tokyo": "Asia/Tokyo",
          "Sydney": "Australia/Sydney", "Auckland": "Pacific/Auckland", "Sao Paulo": "America/Sao_Paulo"}
ALARM_PREFIX = "echo Alarm:"          # alarms are scheduled tasks that print this, so they also work outside this app


# ---------------------------------------------------------------- storage
def load(name, default):
    return appdata.load(name, default) if appdata else default


def save(name, data):
    if appdata:
        appdata.save(name, data)


def user():
    return pyos.userinfo()[0] if pyos else None


# ----------------------------------------------------------------- helpers
def parse_duration(text):
    """'90', '90s', '5m', '1h30m', '25:00' (mm:ss) or '1:30:00' (h:mm:ss) -> seconds."""
    text = text.strip().lower().replace(" ", "")
    if re.fullmatch(r"\d+(:\d{1,2}){1,2}", text):
        parts = [int(p) for p in text.split(":")]
        return parts[0] * 60 + parts[1] if len(parts) == 2 else parts[0] * 3600 + parts[1] * 60 + parts[2]
    if text.isdigit():
        return int(text)
    units = re.findall(r"(\d+)([hms])", text)
    if units and "".join(f"{n}{u}" for n, u in units) == text:
        return sum(int(n) * {"h": 3600, "m": 60, "s": 1}[u] for n, u in units)
    raise ValueError("Try 90s, 5m, 1h30m or 25:00")


def clock_text(seconds):
    seconds = max(0, int(round(seconds)))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def ring(message):
    console.print(f"\n[bold yellow]\a{escape(message)}[/bold yellow]")
    if notify:
        try:
            notify.notify(message, title="Clock", level="success", user=user())
        except Exception:
            pass


# --------------------------------------------------------------- the time
def show_time():
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        ZoneInfo = None
    table = Table(title="World clocks", header_style="bold blue")
    table.add_column("City", style="cyan")
    table.add_column("Time", style="bold")
    table.add_column("Date", style="dim")
    here = datetime.datetime.now().astimezone()
    table.add_row("Here", here.strftime("%H:%M:%S"), here.strftime("%a %d %b") + f"  (UTC{here.strftime('%z')[:3]}:{here.strftime('%z')[3:]})")
    if ZoneInfo:
        for city, zone in CITIES.items():
            try:
                t = datetime.datetime.now(ZoneInfo(zone))
            except Exception:
                continue            # no timezone database on this device
            table.add_row(city, t.strftime("%H:%M"), t.strftime("%a %d %b"))
    else:
        console.print("[dim]This device has no timezone database, so only local time is shown.[/dim]")
    console.print(table)


# ------------------------------------------------------------------ timer
def run_timer(seconds, label="Timer"):
    end = time.time() + seconds
    console.print(f"[dim]{label}: {clock_text(seconds)}. Press Ctrl+C to cancel.[/dim]")
    try:
        with Live(console=console, refresh_per_second=4, transient=True) as live:
            while True:
                left = end - time.time()
                if left <= 0:
                    break
                done = 1 - left / seconds
                bar = "#" * int(done * 30) + "-" * (30 - int(done * 30))
                live.update(Panel(f"[bold cyan]{clock_text(left)}[/bold cyan]\n[dim]{bar}[/dim]", title=label, expand=False))
                time.sleep(0.2)
    except KeyboardInterrupt:
        console.print("[yellow]Timer cancelled.[/yellow]")
        return
    ring(f"{label} finished ({clock_text(seconds)})")


def timer_menu():
    presets = {"1": ("Pomodoro focus", 25 * 60), "2": ("Short break", 5 * 60), "3": ("Long break", 15 * 60), "4": ("Tea", 4 * 60)}
    saved = load("clock_timers", {})
    console.print("Start a timer from a preset, or type a time (90s, 5m, 1h30m, 25:00).")
    for key, (name, secs) in presets.items():
        console.print(f"  [cyan]{key}[/cyan] {name} ({clock_text(secs)})")
    for name, secs in saved.items():
        console.print(f"  [cyan]{escape(name)}[/cyan] ({clock_text(secs)})  [dim]saved[/dim]")
    answer = Prompt.ask("Timer (blank to go back)", default="").strip()
    if not answer:
        return
    if answer in presets:
        run_timer(presets[answer][1], presets[answer][0])
        return
    if answer in saved:
        run_timer(saved[answer], answer)
        return
    try:
        secs = parse_duration(answer)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return
    run_timer(secs)
    name = Prompt.ask("Save this timer as (blank to skip)", default="").strip()
    if name:
        saved[name] = secs
        save("clock_timers", saved)


# -------------------------------------------------------------- stopwatch
def stopwatch():
    console.print("[dim]Stopwatch: Enter = lap, q + Enter = stop.[/dim]")
    start = time.time()
    laps, stop = [], threading.Event()

    def watch():
        with Live(console=console, refresh_per_second=10, transient=True) as live:
            while not stop.is_set():
                live.update(Panel(f"[bold cyan]{time.time() - start:8.2f} s[/bold cyan]  [dim]{len(laps)} lap(s)[/dim]", expand=False))
                time.sleep(0.1)

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    last = start
    try:
        while True:
            try:
                typed = input()
            except EOFError:
                break
            now = time.time()
            if typed.strip().lower() in ("q", "stop"):
                break
            laps.append((now - last, now - start))
            last = now
    except KeyboardInterrupt:
        pass
    stop.set()
    thread.join()
    total = time.time() - start
    table = Table(title=f"Stopped at {total:.2f} s", header_style="bold blue")
    table.add_column("Lap", justify="right")
    table.add_column("Split", justify="right")
    table.add_column("Total", justify="right")
    for i, (split, tot) in enumerate(laps, 1):
        table.add_row(str(i), f"{split:.2f} s", f"{tot:.2f} s")
    console.print(table if laps else f"[bold]Stopped at {total:.2f} s[/bold]")


# ----------------------------------------------------------------- alarms
def alarm_tasks():
    return [t for t in scheduler.tasks_for(user()) if t["command"].startswith(ALARM_PREFIX)] if scheduler else []


def alarms_menu():
    if not scheduler:
        console.print("[yellow]Alarms need PythonOS.[/yellow]")
        return
    while True:
        tasks = alarm_tasks()
        if tasks:
            table = Table(title="Alarms", header_style="bold blue")
            table.add_column("#", justify="right")
            table.add_column("When")
            table.add_column("Label")
            for t in tasks:
                table.add_row(str(t["id"]), scheduler.describe(t), escape(t["command"][len(ALARM_PREFIX):].strip()))
            console.print(table)
        else:
            console.print("[dim]No alarms yet.[/dim]")
        console.print("[dim]Alarms ring (as a notification) while you are logged in, even when this app is closed.[/dim]")
        choice = Prompt.ask("(a)dd  (d)elete  (b)ack", choices=["a", "d", "b"], default="b")
        if choice == "b":
            return
        if choice == "a":
            when = Prompt.ask("Time (HH:MM)").strip()
            repeat = Prompt.ask("Repeat", choices=["daily", "once"], default="daily")
            label = Prompt.ask("Label", default="Alarm").strip() or "Alarm"
            try:
                task = scheduler.add(user(), ["daily" if repeat == "daily" else "at", when, *ALARM_PREFIX.split(), label])
                console.print(f"[green]Alarm #{task['id']} set ({scheduler.describe(task)}).[/green]")
            except ValueError as e:
                console.print(f"[red]{escape(str(e))}[/red]")
        elif choice == "d" and tasks:
            num = Prompt.ask("Alarm number")
            if num.isdigit() and scheduler.remove(user(), int(num)):
                console.print("[green]Deleted.[/green]")
            else:
                console.print("[red]No such alarm.[/red]")


# ------------------------------------------------------------------- main
def main():
    show_time()
    while True:
        choice = Prompt.ask("\n[bold](t)[/bold]ime  t(i)mer  [bold](s)[/bold]topwatch  [bold](a)[/bold]larms  [bold](q)[/bold]uit",
                            choices=["t", "i", "s", "a", "q"], default="q")
        if choice == "q":
            return
        {"t": show_time, "i": timer_menu, "s": stopwatch, "a": alarms_menu}[choice]()


def execute(args=None):
    args = list(args or [])
    if args and args[0] in ("timer", "stopwatch", "alarm", "alarms", "time"):
        sub = args[0]
        if sub == "timer" and len(args) > 1:
            try:
                run_timer(parse_duration(" ".join(args[1:])))
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
            return
        {"timer": timer_menu, "stopwatch": stopwatch, "alarm": alarms_menu, "alarms": alarms_menu, "time": show_time}[sub]()
        return
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute()
