#!/usr/bin/env python3
"""Earthquakes: the latest from the US Geological Survey (earthquake.usgs.gov, no account or key).

    quake                       the significant ones of the past week
    quake day                   today (past 24 hours), magnitude 2.5 and up
    quake month 5               the past month, magnitude 5 and up
Periods: hour, day, week, month.  Magnitudes with a ready-made feed: 1, 2.5, 4.5, or significant.
"""
import sys
import time

import requests
from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()
FEED = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{level}_{period}.geojson"
HEADERS = {"User-Agent": "PythonOS-quake/1.0 (https://github.com/Kalmai221/PythonOS)"}
PERIODS = ("hour", "day", "week", "month")
LEVELS = {"1": "1.0", "2.5": "2.5", "4.5": "4.5"}


def feed_url(period="week", minimum=None):
    """The URL of the ready-made feed. No minimum means the 'significant' feed for a week or month, and 2.5 for shorter periods."""
    if period not in PERIODS:
        raise ValueError("The period is hour, day, week or month.")
    if minimum is None:
        level = "significant" if period in ("week", "month") else "2.5"
    else:
        # the biggest ready-made feed that still includes everything from `minimum` up; parse() cuts the list to `minimum` afterwards
        level = next((LEVELS[k] for k in ("4.5", "2.5", "1") if float(k) <= float(minimum)), "all")
    return FEED.format(level=level, period=period)


def parse(geojson, minimum=None):
    """[(magnitude, place, depth km, time in seconds, link)] with the biggest first."""
    rows = []
    for feature in geojson.get("features", []):
        props, coords = feature.get("properties") or {}, (feature.get("geometry") or {}).get("coordinates") or [0, 0, 0]
        if props.get("mag") is None:
            continue
        if minimum is not None and props["mag"] < minimum:
            continue
        depth = coords[2] if len(coords) > 2 and coords[2] is not None else 0
        rows.append((float(props["mag"]), props.get("place") or "unknown place", float(depth), (props.get("time") or 0) / 1000, props.get("url") or ""))
    return sorted(rows, reverse=True)


def colour(magnitude):
    return "bold red" if magnitude >= 6 else "red" if magnitude >= 5 else "yellow" if magnitude >= 4 else "green"


def main(argv):
    period, minimum = "week", None
    try:
        for word in argv:
            if word in PERIODS:
                period = word
            else:
                minimum = float(word)
        url = feed_url(period, minimum)
    except ValueError as e:
        console.print(__doc__)
        console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    try:
        response = requests.get(url, timeout=15, headers=HEADERS)
        response.raise_for_status()
        rows = parse(response.json(), minimum)
    except (requests.RequestException, ValueError) as e:
        console.print(f"[red]Could not read the earthquake list ({escape(type(e).__name__)}). Check the internet connection.[/red]")
        return 1
    if not rows:
        console.print("No earthquakes in that list.")
        return 0
    table = Table(title=f"Earthquakes, past {period}" + (f", magnitude {minimum:g}+" if minimum is not None else ""))
    for column, justify in (("Mag", "right"), ("Where", "left"), ("Depth", "right"), ("When", "left")):
        table.add_column(column, justify=justify)
    for mag, place, depth, when, _link in rows[:25]:
        table.add_row(f"[{colour(mag)}]{mag:.1f}[/{colour(mag)}]", escape(place), f"{depth:.0f} km", time.strftime("%a %d %b %H:%M", time.localtime(when)))
    console.print(table)
    if len(rows) > 25:
        console.print(f"[dim]{len(rows) - 25} smaller ones are not shown.[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
