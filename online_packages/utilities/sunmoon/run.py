#!/usr/bin/env python3
"""Sun and Moon: sunrise, sunset, day length and the phase of the moon, worked out on this computer (the astral library).

    sunmoon london                  today
    sunmoon "new york" 2026-12-21   a given day
    sunmoon tokyo --week            the next 7 days
Cities are looked up in the library's own list of cities, so no internet is needed.
"""
import datetime
import re
import sys

from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()

# (the phase number stays below this limit, name, symbol); astral counts 0 new moon, 7 first quarter, 14 full moon, 21 last quarter, up to 28
PHASES = [(1, "New moon", "🌑"), (6, "Waxing crescent", "🌒"), (8, "First quarter", "🌓"), (13, "Waxing gibbous", "🌔"), (15, "Full moon", "🌕"),
          (20, "Waning gibbous", "🌖"), (22, "Last quarter", "🌗"), (27, "Waning crescent", "🌘")]


def phase_name(value):
    """(name, symbol) for astral's moon phase number (0 to 27.99)."""
    value = value % 28
    for limit, name, symbol in PHASES:
        if value < limit:
            return name, symbol
    return "New moon", "🌑"


def lit_percent(value):
    """About how much of the moon's face is lit, from the phase number."""
    import math
    return round((1 - math.cos(2 * math.pi * (value % 28) / 28)) / 2 * 100)


def day_length(sunrise, sunset):
    seconds = int((sunset - sunrise).total_seconds())
    return f"{seconds // 3600}h {seconds % 3600 // 60}m"


def find_city(name):
    from astral.geocoder import database, lookup
    return lookup(name, database())


def times_for(city, day):
    """{'sunrise': datetime, 'sunset': datetime, ...} for a day, or {} when the sun does not rise or set that day (polar regions)."""
    from astral.sun import sun
    try:
        return sun(city.observer, date=day, tzinfo=city.timezone)
    except ValueError:
        return {}


def parse(argv):
    argv = list(argv)
    week = "--week" in argv
    if week:
        argv.remove("--week")
    day = datetime.date.today()
    rest = []
    for word in argv:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", word):
            day = datetime.date.fromisoformat(word)
        else:
            rest.append(word)
    if not rest:
        raise ValueError("")
    return " ".join(rest), day, week


def main(argv):
    try:
        name, day, week = parse(argv)
    except ValueError as e:
        console.print(__doc__)
        if str(e):
            console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    try:
        city = find_city(name)
        from astral.moon import phase
    except ImportError:
        console.print("[red]The 'astral' library is not installed. Install this app again to get it.[/red]")
        return 1
    except Exception:                                           # noqa: BLE001 - astral raises KeyError for a city it does not know
        console.print(f"[red]I do not know the city '{escape(name)}'. Try a bigger city nearby, or the capital of the country.[/red]")
        return 1
    table = Table(title=f"{city.name}, {city.region}  ({city.timezone})")
    for column in ("Day", "Sunrise", "Sunset", "Daylight", "Moon"):
        table.add_column(column)
    for offset in range(7 if week else 1):
        d = day + datetime.timedelta(days=offset)
        t = times_for(city, d)
        moon = phase(d)
        label, symbol = phase_name(moon)
        if t:
            table.add_row(f"{d:%a %d %b}", f"{t['sunrise']:%H:%M}", f"{t['sunset']:%H:%M}", day_length(t["sunrise"], t["sunset"]),
                          f"{symbol} {label} ({lit_percent(moon)}% lit)")
        else:
            table.add_row(f"{d:%a %d %b}", "-", "-", "polar day or night", f"{symbol} {label} ({lit_percent(moon)}% lit)")
    console.print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
