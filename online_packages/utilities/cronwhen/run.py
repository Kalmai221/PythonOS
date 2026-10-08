#!/usr/bin/env python3
"""Cron explainer: what a cron schedule means, and when it runs next (cron-descriptor and croniter).

    cronwhen "*/15 9-17 * * 1-5"            in plain words, and the next 5 times
    cronwhen "0 3 * * 0" -n 10              the next 10 times
    cronwhen "@daily"                       the usual shortcuts work
Five fields: minute hour day-of-month month day-of-week. Times are this computer's local time.
"""
import datetime
import sys

from rich.console import Console
from rich.markup import escape

console = Console()

SHORTCUTS = {"@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *", "@weekly": "0 0 * * 0", "@daily": "0 0 * * *",
             "@midnight": "0 0 * * *", "@hourly": "0 * * * *"}


def normalise(expression):
    """The five-field form of an expression (the @shortcuts are expanded). Raises ValueError when it is not five fields."""
    text = " ".join(expression.split())
    text = SHORTCUTS.get(text.lower(), text)
    if len(text.split()) != 5:
        raise ValueError("A cron schedule has five fields: minute hour day-of-month month day-of-week (or a shortcut such as @daily).")
    return text


def explain(expression):
    from cron_descriptor import get_description
    return get_description(normalise(expression))


def upcoming(expression, count=5, start=None):
    """The next `count` run times after `start` (default: now)."""
    from croniter import croniter
    it = croniter(normalise(expression), start or datetime.datetime.now())
    return [it.get_next(datetime.datetime) for _ in range(max(1, min(count, 50)))]


def parse(argv):
    argv = list(argv)
    count = 5
    if "-n" in argv:
        i = argv.index("-n")
        try:
            count = int(argv[i + 1])
        except (IndexError, ValueError):
            raise ValueError("-n needs a number") from None
        del argv[i:i + 2]
    if not argv:
        raise ValueError("")
    return " ".join(argv), count


def main(argv):
    try:
        expression, count = parse(argv)
    except ValueError as e:
        console.print(__doc__)
        if str(e):
            console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    try:
        words = explain(expression)
        times = upcoming(expression, count)
    except ImportError:
        console.print("[red]The cron libraries are not installed. Install this app again to get them.[/red]")
        return 1
    except Exception as e:                                       # noqa: BLE001 - the libraries raise their own error types for a bad schedule
        console.print(f"[red]Not a valid schedule: {escape(str(e))}[/red]")
        return 1
    console.print(f"[bold]{escape(normalise(expression))}[/bold]\n{escape(words)}\n")
    now = datetime.datetime.now()
    for t in times:
        delta = t - now
        mins = int(delta.total_seconds() // 60)
        console.print(f"  {t:%a %d %b %Y %H:%M}   [dim]in {mins // 1440}d {mins % 1440 // 60}h {mins % 60}m[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
