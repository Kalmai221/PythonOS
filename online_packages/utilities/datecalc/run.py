#!/usr/bin/env python3
"""Date calculator: days between two dates, add or subtract days/weeks/months/years, what day of the week a date is, how old someone is,
and how long until an event. Dates look like 2026-12-25, 25/12/2026, 'today', 'tomorrow', or '+30' (30 days from now).
Usage: datecalc between <date> <date>  |  datecalc add <date> <amount> (like 3m, 2w, -10d)  |  datecalc day <date>  |
datecalc age <birthday>  |  datecalc until <date>  (no arguments opens a menu)."""
import calendar
import datetime
import re
import sys

from rich.console import Console
from rich.prompt import Prompt

console = Console()


def parse_date(text, today=None):
    today = today or datetime.date.today()
    text = text.strip().lower()
    if text in ("", "today", "now"):
        return today
    if text == "tomorrow":
        return today + datetime.timedelta(days=1)
    if text == "yesterday":
        return today - datetime.timedelta(days=1)
    m = re.fullmatch(r"([+-])(\d+)", text)
    if m:
        return today + datetime.timedelta(days=int(m.group(2)) * (1 if m.group(1) == "+" else -1))
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y"):
        try:
            return datetime.datetime.strptime(text.replace(",", ""), fmt).date()
        except ValueError:
            pass
    weekday = re.fullmatch(r"(next|last)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", text)
    if weekday:
        names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        target = names.index(weekday.group(2))
        if weekday.group(1) == "last":
            return today - datetime.timedelta(days=(today.weekday() - target) % 7 or 7)
        return today + datetime.timedelta(days=(target - today.weekday()) % 7 or (7 if weekday.group(1) else 0))
    try:                                                   # python-dateutil, when installed, understands almost anything people write
        from dateutil import parser as dateparser
        return dateparser.parse(text, default=datetime.datetime.combine(today, datetime.time())).date()
    except (ImportError, ValueError, OverflowError):
        pass
    raise ValueError(f"'{text}' is not a date. Try 2026-12-25, 25/12/2026, today, tomorrow, next friday or +30.")


def add_months(date, months):
    """Move by whole months, keeping the day (or the last day of a short month)."""
    index = date.year * 12 + date.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    return date.replace(year=year, month=month, day=min(date.day, calendar.monthrange(year, month)[1]))


def parse_amount(text):
    """'3m' -> ('months', 3); '2w', '10d', '1y', '-5d'. Returns (unit, signed number)."""
    m = re.fullmatch(r"([+-]?\d+)\s*([dwmy])?", text.strip().lower())
    if not m:
        raise ValueError("Give an amount like 10d (days), 2w (weeks), 3m (months) or 1y (years).")
    return {"d": "days", "w": "weeks", "m": "months", "y": "years", None: "days"}[m.group(2)], int(m.group(1))


def add(date, unit, n):
    if unit == "days":
        return date + datetime.timedelta(days=n)
    if unit == "weeks":
        return date + datetime.timedelta(weeks=n)
    return add_months(date, n * (12 if unit == "years" else 1))


def difference(a, b):
    """(years, months, days) from the earlier to the later date, plus the total days."""
    if a > b:
        a, b = b, a
    years = b.year - a.year - ((b.month, b.day) < (a.month, a.day))
    anchor = add_months(a, years * 12)
    months = (b.year - anchor.year) * 12 + b.month - anchor.month - (b.day < anchor.day)
    anchor = add_months(anchor, months)
    return years, months, (b - anchor).days, (b - a).days


def business_days(a, b):
    if a > b:
        a, b = b, a
    return sum(1 for i in range((b - a).days) if (a + datetime.timedelta(days=i)).weekday() < 5)


def describe_difference(a, b):
    y, m, d, total = difference(a, b)
    parts = [f"{n} {name}{'' if n == 1 else 's'}" for n, name in ((y, "year"), (m, "month"), (d, "day")) if n]
    return (", ".join(parts) or "the same day") + f"  ({total} days, {total // 7} weeks and {total % 7} days, {business_days(a, b)} working days)"


def name_of(date):
    return date.strftime("%A %d %B %Y")


def main(args):
    today = datetime.date.today()
    if not args:
        while True:
            choice = Prompt.ask("(b)etween two dates, (a)dd to a date, (d)ay of the week, a(g)e, (u)ntil an event, (q)uit",
                                choices=["b", "a", "d", "g", "u", "q"], default="b")
            if choice == "q":
                return
            try:
                if choice == "b":
                    run(["between", Prompt.ask("From"), Prompt.ask("To", default="today")])
                elif choice == "a":
                    run(["add", Prompt.ask("Date", default="today"), Prompt.ask("Amount (like 30d, 2w, 3m, 1y, -10d)")])
                elif choice == "d":
                    run(["day", Prompt.ask("Date")])
                elif choice == "g":
                    run(["age", Prompt.ask("Birthday")])
                else:
                    run(["until", Prompt.ask("Event date")])
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
        return
    run(args)


def run(args):
    today = datetime.date.today()
    cmd = args[0].lower()
    if cmd == "between" and len(args) >= 3:
        a, b = parse_date(args[1]), parse_date(args[2])
        console.print(f"{name_of(a)}  ->  {name_of(b)}\n{describe_difference(a, b)}")
    elif cmd == "add" and len(args) >= 3:
        date = parse_date(args[1])
        unit, n = parse_amount(args[2])
        console.print(f"{name_of(date)} {'+' if n >= 0 else '-'} {abs(n)} {unit} = [bold]{name_of(add(date, unit, n))}[/bold]")
    elif cmd == "day" and len(args) >= 2:
        d = parse_date(args[1])
        console.print(f"{name_of(d)}  (day {d.timetuple().tm_yday} of the year, week {d.isocalendar()[1]})")
    elif cmd == "age" and len(args) >= 2:
        born = parse_date(args[1])
        if born > today:
            raise ValueError("That date is in the future.")
        y, m, d, total = difference(born, today)
        console.print(f"Age: [bold]{y} years, {m} months, {d} days[/bold]  ({total:,} days old)")
        nxt = born.replace(year=today.year) if not (born.month == 2 and born.day == 29) else datetime.date(today.year, 3, 1)
        if nxt < today:
            nxt = nxt.replace(year=today.year + 1) if not (born.month == 2 and born.day == 29) else datetime.date(today.year + 1, 3, 1)
        console.print(f"Next birthday: {name_of(nxt)} (in {(nxt - today).days} days)")
    elif cmd == "until" and len(args) >= 2:
        d = parse_date(args[1])
        days = (d - today).days
        console.print(f"{name_of(d)} is " + ("today!" if days == 0 else f"in [bold]{days}[/bold] days ({describe_difference(today, d)})" if days > 0
                                              else f"[bold]{-days}[/bold] days ago"))
    else:
        console.print("datecalc [between <date> <date> | add <date> <amount> | day <date> | age <birthday> | until <date>]")


def execute(args=None):
    try:
        main(list(args or []))
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
