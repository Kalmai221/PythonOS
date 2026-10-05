#!/usr/bin/env python3
"""Weather: current conditions and a three-day forecast for any city (data from wttr.in). Remembers your city and
your unit choice, and shows the last forecast it saw when you are offline."""
import sys
import time

import requests
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
FILE = "weather"


def load():
    return (appdata.load(FILE, {}) if appdata else {}) or {}


def save(data):
    if appdata:
        appdata.save(FILE, data)


def fetch(city):
    response = requests.get(f"https://wttr.in/{requests.utils.quote(city)}?format=j1", timeout=10)
    response.raise_for_status()
    return response.json()


def temp(day_or_now, key, imperial):
    return f"{day_or_now[key + ('_F' if imperial else '_C')]}{'F' if imperial else 'C'}"


def render(data, imperial, note=""):
    now = data["current_condition"][0]
    area = data["nearest_area"][0]
    place = f"{area['areaName'][0]['value']}, {area['country'][0]['value']}"
    speed = f"{now['windspeedMiles']} mph" if imperial else f"{now['windspeedKmph']} km/h"
    dist = f"{now['visibilityMiles']} mi" if imperial else f"{now['visibility']} km"
    body = (f"[bold]{escape(now['weatherDesc'][0]['value'])}[/bold]\n\n"
            f"Temperature : {temp(now, 'temp', imperial)} (feels like {temp(now, 'FeelsLike', imperial)})\n"
            f"Humidity    : {now['humidity']}%\n"
            f"Wind        : {speed} {now['winddir16Point']}\n"
            f"Visibility  : {dist}\n"
            f"UV index    : {now.get('uvIndex', '?')}")
    console.print(Panel(body, title=f"[bold cyan]{escape(place)}[/bold cyan]", subtitle=note or None, border_style="blue", expand=False))
    table = Table(title="Forecast", header_style="bold blue")
    for col in ("Day", "Low", "High", "Sky", "Rain"):
        table.add_column(col)
    for day in data.get("weather", [])[:3]:
        hourly = day.get("hourly", [])
        mid = hourly[len(hourly) // 2] if hourly else {}
        sky = mid.get("weatherDesc", [{"value": ""}])[0]["value"]
        rain = max([int(h.get("chanceofrain", 0)) for h in hourly] or [0])
        table.add_row(day["date"], temp(day, "mintemp", imperial), temp(day, "maxtemp", imperial), escape(sky), f"{rain}%")
    console.print(table)


def show(city, settings):
    imperial = settings.get("units") == "imperial"
    try:
        with console.status("Fetching weather..."):
            data = fetch(city)
        settings.update(city=city, last={"city": city, "time": time.time(), "data": data})
        save(settings)
        render(data, imperial)
    except requests.RequestException:
        last = settings.get("last")
        if last and last.get("city", "").lower() == city.lower():
            age = int((time.time() - last["time"]) // 60)
            console.print("[yellow]Could not reach the weather service; showing the last forecast we saw.[/yellow]")
            render(last["data"], imperial, note=f"saved {age} min ago")
        else:
            console.print("[bold red]Could not reach the weather service. Check your internet connection.[/bold red]")
    except (KeyError, IndexError, ValueError):
        console.print(f"[bold red]No weather found for '{escape(city)}'.[/bold red]")


def main(city=None):
    settings = load()
    if not city:
        city = Prompt.ask("City", default=settings.get("city") or "London").strip()
    if not city:
        return
    show(city, settings)
    while True:
        choice = Prompt.ask("(c)ity  (u)nits  (r)efresh  (q)uit",
                            choices=["c", "u", "r", "q"], default="q")
        if choice == "q":
            return
        if choice == "u":
            settings["units"] = "metric" if settings.get("units") == "imperial" else "imperial"
            save(settings)
        elif choice == "c":
            city = Prompt.ask("City", default=city).strip() or city
        show(city, settings)


def execute(args=None):
    try:
        main(" ".join(args) if args else None)
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
