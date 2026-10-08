#!/usr/bin/env python3
"""Holidays: the public holidays of a country (the holidays library, which works offline).

    holidays US                   this year's holidays in the United States
    holidays DE 2027              a given year
    holidays GB next              the next holiday from today
    holidays FR 2026-07-14        is that day a holiday?
    holidays US --state CA        a state or region (see --regions US)
    holidays --countries          the country codes it knows
Use the two-letter country code (US, GB, DE, FR, JP, ...).
"""
import datetime
import re
import sys

from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()


def load():
    try:
        import holidays
    except ImportError:
        console.print("[red]The 'holidays' library is not installed. Install this app again to get it.[/red]")
        sys.exit(1)
    return holidays


def calendar(holidays, code, year, subdiv=None):
    """{date: name} for a country and year. Raises NotImplementedError for an unknown country or region."""
    return holidays.country_holidays(code.upper(), subdiv=subdiv, years=year)


def year_list(holidays, code, year, subdiv=None):
    """[(date, name)] sorted by date."""
    return sorted(calendar(holidays, code, year, subdiv).items())


def next_holiday(holidays, code, today, subdiv=None):
    """(date, name) of the first holiday on or after `today`, looking into next year when needed; None if there is none."""
    for year in (today.year, today.year + 1):
        for day, name in year_list(holidays, code, year, subdiv):
            if day >= today:
                return day, name
    return None


def parse_args(argv):
    """-> (code, year, date, mode, subdiv). mode is 'year', 'next', 'date', 'countries' or 'regions'."""
    argv = list(argv)
    subdiv = None
    for flag in ("--state", "--region"):
        if flag in argv:
            i = argv.index(flag)
            subdiv = argv[i + 1] if i + 1 < len(argv) else None
            del argv[i:i + 2]
    if "--countries" in argv:
        return None, None, None, "countries", subdiv
    if "--regions" in argv:
        argv.remove("--regions")
        return (argv[0] if argv else None), None, None, "regions", subdiv
    if not argv:
        raise ValueError("Give a country code, for example: holidays US")
    code, rest = argv[0], argv[1:]
    year, day, mode = datetime.date.today().year, None, "year"
    for word in rest:
        if word.lower() == "next":
            mode = "next"
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", word):
            day, mode = datetime.date.fromisoformat(word), "date"
        elif re.fullmatch(r"\d{4}", word):
            year = int(word)
        else:
            raise ValueError(f"I do not understand '{word}'.")
    return code, year, day, mode, subdiv


def main(argv):
    try:
        code, year, day, mode, subdiv = parse_args(argv)
    except ValueError as e:
        console.print(__doc__ if "Give" in str(e) else "")
        console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    holidays = load()
    try:
        if mode == "countries":
            names = sorted(holidays.list_supported_countries())
            console.print(" ".join(names))
            return 0
        if mode == "regions":
            supported = holidays.list_supported_countries()
            regions = supported.get((code or "").upper()) if isinstance(supported, dict) else None
            console.print(" ".join(regions) if regions else "No regions for that country (or it is not supported).")
            return 0
        if mode == "next":
            found = next_holiday(holidays, code, datetime.date.today(), subdiv)
            if not found:
                console.print("No holiday found.")
                return 1
            days = (found[0] - datetime.date.today()).days
            when = "today" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
            console.print(f"[bold]{escape(found[1])}[/bold] - {found[0]:%A %d %B %Y} ({when})")
            return 0
        if mode == "date":
            name = calendar(holidays, code, day.year, subdiv).get(day)
            console.print(f"{day:%A %d %B %Y}: " + (f"[bold green]{escape(name)}[/bold green]" if name else "not a public holiday"))
            return 0
        table = Table(title=f"Public holidays {code.upper()} {year}" + (f" ({subdiv})" if subdiv else ""))
        table.add_column("Date")
        table.add_column("Day")
        table.add_column("Holiday")
        for d, name in year_list(holidays, code, year, subdiv):
            table.add_row(f"{d:%d %b}", f"{d:%a}", escape(name))
        console.print(table)
        return 0
    except NotImplementedError:
        console.print(f"[red]I do not know the country or region '{escape(str(code))}'. See: holidays --countries[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
