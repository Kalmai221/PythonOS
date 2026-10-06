import datetime
import re

from rich.console import Console

from pyos import optional

console = Console()
config = {"name": "date", "description": "Show the date and time (date [-d <text>] [+format]); -d understands 'tomorrow', 'next friday', '+3 days', '2026-12-25'."}

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def parse(text, now=None):
    """A datetime for what a person wrote ('tomorrow', 'next friday', '3 days ago', '+2 weeks', '2026-12-25 18:30'), or None. python-dateutil,
    when installed, understands anything else."""
    now = now or datetime.datetime.now()
    word = text.strip().lower()
    if word in ("now", ""):
        return now
    base = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if word == "today":
        return base
    if word == "tomorrow":
        return base + datetime.timedelta(days=1)
    if word == "yesterday":
        return base - datetime.timedelta(days=1)
    match = re.fullmatch(r"(next|last|this)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", word)
    if match:
        target = DAYS.index(match.group(2))
        ahead = (target - base.weekday()) % 7
        if match.group(1) == "last":
            return base - datetime.timedelta(days=(base.weekday() - target) % 7 or 7)
        return base + datetime.timedelta(days=ahead or (7 if match.group(1) == "next" else 0))
    match = re.fullmatch(r"(?:in\s+)?([+-]?)\s*(\d+)\s*(second|minute|hour|day|week|month|year)s?(\s+ago)?", word)
    if match:
        count = int(match.group(2)) * (-1 if match.group(1) == "-" or match.group(4) else 1)
        unit = match.group(3)
        if unit in ("month", "year"):
            relativedelta = optional.get("dateutil.relativedelta")
            if relativedelta is not None:
                return now + relativedelta.relativedelta(**{unit + "s": count})
            months = count * (12 if unit == "year" else 1)
            total = now.year * 12 + now.month - 1 + months
            year, month = divmod(total, 12)
            day = min(now.day, [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month])
            return now.replace(year=year, month=month + 1, day=day)
        return now + datetime.timedelta(**{unit + "s": count})
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y", "%d %B %Y", "%B %d %Y"):
        try:
            return datetime.datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    parser = optional.get("dateutil.parser")
    if parser is not None:
        try:
            return parser.parse(text, default=base)
        except (ValueError, OverflowError):
            return None
    return None


def execute(args=None):
    args = list(args or [])
    when, fmt = datetime.datetime.now(), None
    if args and args[0] == "-d":
        text = " ".join(a for a in args[1:] if not a.startswith("+"))
        when = parse(text)
        if when is None:
            console.print(f"[bold red]date: I do not understand '{text}'.[/bold red] Try: tomorrow, next friday, 3 days ago, +2 weeks, 2026-12-25."
                          + ("" if optional.have("dateutil") else " (Install python-dateutil for more.)"))
            return False
    fmt = next((a[1:] for a in args if a.startswith("+")), None)
    console.print(when.strftime(fmt) if fmt else when.strftime("%A %Y-%m-%d %H:%M:%S"), markup=False, highlight=False)
    return True
