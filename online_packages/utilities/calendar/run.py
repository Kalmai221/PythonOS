#!/usr/bin/env python3
"""Calendar: a month view, events and reminders. Reminders arrive as notifications when they come due."""
import calendar
import datetime
import re

from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt
from rich.table import Table

try:
    from pyos import appdata, notify, scheduler
    import pyos
except ImportError:
    appdata = notify = scheduler = pyos = None

console = Console()
FILE = "calendar"


def load():
    return (appdata.load(FILE, []) if appdata else []) or []


def save(events):
    if appdata:
        appdata.save(FILE, events)


def parse_date(text, today=None):
    """today, tomorrow, +3 (days), 'fri', 2026-12-25, 25/12 or 25/12/2026 -> date."""
    today = today or datetime.date.today()
    text = text.strip().lower()
    if text in ("", "today"):
        return today
    if text == "tomorrow":
        return today + datetime.timedelta(days=1)
    if re.fullmatch(r"\+\d+", text):
        return today + datetime.timedelta(days=int(text[1:]))
    days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    if text[:3] in days and len(text) <= 9:
        ahead = (days.index(text[:3]) - today.weekday()) % 7 or 7
        return today + datetime.timedelta(days=ahead)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m"):
        try:
            d = datetime.datetime.strptime(text, fmt).date()
            return d.replace(year=today.year) if fmt == "%d/%m" else d
        except ValueError:
            pass
    raise ValueError("Try today, tomorrow, +3, fri, 2026-12-25 or 25/12")


def parse_time(text):
    text = text.strip()
    if not text:
        return ""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise ValueError("Use HH:MM, for example 14:30")
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def month_view(year, month, events):
    marked = {datetime.date.fromisoformat(e["date"]).day for e in events
              if e["date"][:7] == f"{year:04d}-{month:02d}"}
    today = datetime.date.today()
    table = Table(title=f"{calendar.month_name[month]} {year}", header_style="bold blue", expand=False)
    for name in ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"):
        table.add_column(name, justify="right")
    for week in calendar.Calendar(0).monthdayscalendar(year, month):
        cells = []
        for day in week:
            if not day:
                cells.append("")
                continue
            text = f"{day:2d}"
            if day in marked:
                text += "*"
            if (year, month, day) == (today.year, today.month, today.day):
                text = f"[reverse]{text}[/reverse]"
            elif day in marked:
                text = f"[yellow]{text}[/yellow]"
            cells.append(text)
        table.add_row(*cells)
    console.print(table)
    console.print("[dim]* = has events[/dim]")


def list_events(events, upcoming_only=True):
    today = datetime.date.today().isoformat()
    shown = sorted((e for e in events if not upcoming_only or e["date"] >= today), key=lambda e: (e["date"], e.get("time", "")))
    if not shown:
        console.print("[dim]No events. Press 'a' to add one.[/dim]")
        return
    table = Table(title="Events" if not upcoming_only else "Upcoming events", header_style="bold blue")
    for col in ("#", "Date", "Time", "Event", "Remind"):
        table.add_column(col)
    for e in shown:
        d = datetime.date.fromisoformat(e["date"])
        table.add_row(str(e["id"]), d.strftime("%a %d %b %Y"), e.get("time") or "all day", escape(e["title"]),
                      f"{e['remind']} min before" if e.get("remind") is not None else "-")
    console.print(table)


def add_event(events, date_text=None):
    try:
        date = parse_date(date_text if date_text is not None else Prompt.ask("Date", default="today"))
        time_text = parse_time(Prompt.ask("Time (HH:MM, blank = all day)", default=""))
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return
    title = Prompt.ask("What").strip()
    if not title:
        return
    remind = None
    if Prompt.ask("Remind me?", choices=["y", "n"], default="y") == "y":
        answer = Prompt.ask("Minutes before (0 = at the time; all-day events remind at 08:00)", default="10")
        remind = int(answer) if answer.isdigit() else 10
    event = {"id": max([e["id"] for e in events] + [0]) + 1, "date": date.isoformat(), "time": time_text,
             "title": title, "remind": remind, "reminded": False}
    events.append(event)
    save(events)
    console.print(f"[green]Added '{escape(title)}' on {date.strftime('%a %d %b')}.[/green]")
    schedule_soon(event)


def schedule_soon(event):
    """An event whose reminder falls in the next 24 hours also gets a scheduled task, so it rings even when this app is closed."""
    if not scheduler or event.get("remind") is None or not event.get("time"):
        return
    at = datetime.datetime.combine(datetime.date.fromisoformat(event["date"]), datetime.time(*map(int, event["time"].split(":"))))
    trigger = at - datetime.timedelta(minutes=event["remind"])
    now = datetime.datetime.now()
    if now < trigger <= now + datetime.timedelta(hours=24):
        try:
            scheduler.add(pyos.userinfo()[0], ["at", trigger.strftime("%H:%M"), "echo", "Reminder:", event["title"], "at", event["time"]])
            console.print(f"[dim]It will also ring at {trigger.strftime('%H:%M')} while you are logged in.[/dim]")
        except ValueError:
            pass


def due_reminders(events, now=None):
    """Events whose reminder time has passed and that have not been announced yet."""
    now = now or datetime.datetime.now()
    due = []
    for e in events:
        if e.get("remind") is None or e.get("reminded"):
            continue
        day = datetime.date.fromisoformat(e["date"])
        at = datetime.datetime.combine(day, datetime.time(*map(int, e["time"].split(":")))) if e.get("time") \
            else datetime.datetime.combine(day, datetime.time(8, 0))
        trigger = at - datetime.timedelta(minutes=e["remind"] if e.get("time") else 0)
        if now >= trigger and now < at + datetime.timedelta(days=1):
            due.append(e)
    return due


def check_reminders(events):
    """Announce reminders that are due (they are also shown right here so you never miss one)."""
    due = due_reminders(events)
    for e in due:
        when = f" at {e['time']}" if e.get("time") else " (today)" if e["date"] == datetime.date.today().isoformat() else f" on {e['date']}"
        text = f"{e['title']}{when}"
        console.print(f"[bold yellow]Reminder:[/bold yellow] {escape(text)}")
        if notify:
            try:
                notify.notify(text, title="Calendar", level="warn", user=pyos.userinfo()[0])
            except Exception:
                pass
        e["reminded"] = True
    if due:
        save(events)


def main():
    events = load()
    check_reminders(events)
    today = datetime.date.today()
    year, month = today.year, today.month
    month_view(year, month, events)
    list_events(events)
    while True:
        choice = Prompt.ask("(p)rev  (n)ext  (t)oday  (a)dd  (l)ist all  (d)elete  (q)uit",
                            choices=["p", "n", "t", "a", "l", "d", "q"], default="q")
        if choice == "q":
            return
        if choice in ("p", "n"):
            month += -1 if choice == "p" else 1
            if month == 0:
                year, month = year - 1, 12
            elif month == 13:
                year, month = year + 1, 1
            month_view(year, month, events)
        elif choice == "t":
            year, month = today.year, today.month
            month_view(year, month, events)
            list_events(events)
        elif choice == "a":
            add_event(events)
        elif choice == "l":
            list_events(events, upcoming_only=False)
        elif choice == "d":
            num = Prompt.ask("Event number")
            before = len(events)
            events[:] = [e for e in events if str(e["id"]) != num.strip()]
            save(events)
            console.print("[green]Deleted.[/green]" if len(events) < before else "[red]No such event.[/red]")


def execute(args=None):
    args = list(args or [])
    events = load()
    if args and args[0] in ("today", "agenda"):
        check_reminders(events)
        today = datetime.date.today().isoformat()
        list_events([e for e in events if e["date"] == today], upcoming_only=False)
        return
    if args and args[0] == "add":
        add_event(events, date_text=args[1] if len(args) > 1 else None)
        return
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute()
