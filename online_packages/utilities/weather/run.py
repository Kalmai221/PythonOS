#!/usr/bin/env python3
"""Weather: current conditions, an hourly forecast and a three-day outlook for any city (data from wttr.in), several saved cities, warnings for
severe weather, Celsius or Fahrenheit, and a one-line summary for the prompt. The last forecast of each city is kept for offline use.
Usage: weather [city]  |  weather hourly [city]  |  weather --short  |  weather all  |  weather cities  |  weather add <city>  |  weather remove <city>"""
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
CACHE_MAX_AGE = 30 * 60


def load():
    return (appdata.load(FILE, {}) if appdata else {}) or {}


def save(data):
    if appdata:
        appdata.save(FILE, data)


def fetch(city):
    response = requests.get(f"https://wttr.in/{requests.utils.quote(city)}?format=j1", timeout=10)
    response.raise_for_status()
    return response.json()


def get_forecast(city, settings, max_age=0):
    """(data, age in seconds, error). Uses the saved copy when it is younger than max_age or when the network is down."""
    cached = (settings.get("cache") or {}).get(city.lower())
    if cached and time.time() - cached["time"] <= max_age:
        return cached["data"], time.time() - cached["time"], None
    try:
        data = fetch(city)
        data["current_condition"][0]
        settings.setdefault("cache", {})[city.lower()] = {"time": time.time(), "data": data}
        for old in sorted(settings["cache"], key=lambda k: settings["cache"][k]["time"])[:-8]:      # at most 8 cities are kept
            del settings["cache"][old]
        save(settings)
        return data, 0, None
    except requests.RequestException:
        if cached:
            return cached["data"], time.time() - cached["time"], "offline"
        return None, 0, "offline"
    except (KeyError, IndexError, ValueError):
        return None, 0, "notfound"


def t(value, key, imperial):
    """A temperature field as text. wttr.in names them temp_C, FeelsLikeC, tempC, mintempC ... depending on where they sit."""
    unit = "F" if imperial else "C"
    for name in (f"{key}_{unit}", f"{key}{unit}"):
        if name in value:
            return f"{value[name]}{unit}"
    return "?"


def alerts(data):
    """Warnings worth knowing about in the next three days, worked out from the forecast numbers: [(colour, text)]."""
    found = []
    for day in data.get("weather", [])[:3]:
        label = day["date"]
        hourly = day.get("hourly", [])
        gust = max([int(h.get("WindGustKmph", 0)) for h in hourly] or [0])
        rain = max([int(h.get("chanceofrain", 0)) for h in hourly] or [0])
        precip = sum(float(h.get("precipMM", 0)) for h in hourly)
        thunder = max([int(h.get("chanceofthunder", 0)) for h in hourly] or [0])
        snow = max([int(h.get("chanceofsnow", 0)) for h in hourly] or [0])
        hot, cold = int(day.get("maxtempC", 0)), int(day.get("mintempC", 0))
        if gust >= 90:
            found.append(("red", f"{label}: violent gusts up to {gust} km/h"))
        elif gust >= 60:
            found.append(("dark_orange", f"{label}: strong wind, gusts up to {gust} km/h"))
        if precip >= 25 and rain >= 70:
            found.append(("dark_orange", f"{label}: heavy rain expected ({precip:.0f} mm)"))
        if thunder >= 60:
            found.append(("red", f"{label}: thunderstorms likely ({thunder}%)"))
        if snow >= 60:
            found.append(("dark_orange", f"{label}: snow likely ({snow}%)"))
        if hot >= 35:
            found.append(("red", f"{label}: extreme heat, up to {hot} C"))
        if cold <= -10:
            found.append(("red", f"{label}: severe cold, down to {cold} C"))
    return found


def short_line(data, imperial, name=None):
    now = data["current_condition"][0]
    place = name or data["nearest_area"][0]["areaName"][0]["value"]
    return f"{place}: {t(now, 'temp', imperial)}, {now['weatherDesc'][0]['value']}"


def render_current(data, imperial, note=""):
    now = data["current_condition"][0]
    area = data["nearest_area"][0]
    place = f"{area['areaName'][0]['value']}, {area['country'][0]['value']}"
    speed = f"{now['windspeedMiles']} mph" if imperial else f"{now['windspeedKmph']} km/h"
    dist = f"{now['visibilityMiles']} mi" if imperial else f"{now['visibility']} km"
    body = (f"[bold]{escape(now['weatherDesc'][0]['value'])}[/bold]\n\n"
            f"Temperature : {t(now, 'temp', imperial)} (feels like {t(now, 'FeelsLike', imperial)})\n"
            f"Humidity    : {now['humidity']}%\n"
            f"Wind        : {speed} {now['winddir16Point']}\n"
            f"Visibility  : {dist}\n"
            f"UV index    : {now.get('uvIndex', '?')}")
    console.print(Panel(body, title=f"[bold cyan]{escape(place)}[/bold cyan]", subtitle=note or None, border_style="blue", expand=False))
    for colour, text in alerts(data):
        console.print(f"[bold {colour}]Warning: {escape(text)}[/bold {colour}]")


def render_days(data, imperial):
    table = Table(title="Forecast", header_style="bold blue")
    for col in ("Day", "Low", "High", "Sky", "Rain"):
        table.add_column(col)
    for day in data.get("weather", [])[:3]:
        hourly = day.get("hourly", [])
        mid = hourly[len(hourly) // 2] if hourly else {}
        sky = mid.get("weatherDesc", [{"value": ""}])[0]["value"]
        rain = max([int(h.get("chanceofrain", 0)) for h in hourly] or [0])
        table.add_row(day["date"], t(day, "mintemp", imperial), t(day, "maxtemp", imperial), escape(sky), f"{rain}%")
    console.print(table)


def render_hourly(data, imperial, hours=24):
    """The next `hours` hours in 3-hour steps."""
    now = time.localtime()
    rows = []
    for day_index, day in enumerate(data.get("weather", [])[:3]):
        for h in day.get("hourly", []):
            slot = int(h["time"]) // 100
            if day_index == 0 and slot + 3 <= now.tm_hour:
                continue
            rows.append((day["date"], slot, h))
    table = Table(title="Hourly forecast", header_style="bold blue")
    for col in ("When", "Temp", "Feels", "Sky", "Rain", "Wind"):
        table.add_column(col)
    for date, slot, h in rows[:hours // 3 + 1]:
        wind = f"{h['windspeedMiles']} mph" if imperial else f"{h['windspeedKmph']} km/h"
        table.add_row(f"{date[5:]} {slot:02d}:00", t(h, "temp", imperial), t(h, "FeelsLike", imperial), escape(h["weatherDesc"][0]["value"]),
                      f"{h.get('chanceofrain', 0)}%", wind)
    console.print(table)


def show(city, settings, mode="current"):
    imperial = settings.get("units") == "imperial"
    data, age, error = get_forecast(city, settings, max_age=CACHE_MAX_AGE if mode == "short" else 0)
    if data is None:
        console.print("[bold red]Could not reach the weather service. Check your internet connection.[/bold red]" if error == "offline"
                      else f"[bold red]No weather found for '{escape(city)}'.[/bold red]")
        return False
    if error == "offline" and mode != "short":
        console.print("[yellow]Could not reach the weather service; showing the last forecast we saw.[/yellow]")
    if mode == "short":
        console.print(short_line(data, imperial), markup=False, highlight=False)
        return True
    render_current(data, imperial, f"saved {int(age // 60)} min ago" if age > 60 else "")
    (render_hourly if mode == "hourly" else render_days)(data, imperial)
    return True


def cities(settings):
    saved = list(settings.get("cities", []))
    default = settings.get("city")
    return ([default] if default and default not in saved else []) + saved


def main(args):
    settings = load()
    flags = [a for a in args if a.startswith("-")]
    words = [a for a in args if not a.startswith("-")]
    if "--short" in flags or "-s" in flags:
        city = " ".join(words) or (cities(settings) or [""])[0]
        if not city:
            console.print("weather: no city saved yet (run: weather London)", markup=False)
            return
        show(city, settings, "short")
        return
    sub = words[0].lower() if words else ""
    if sub == "cities":
        for c in cities(settings):
            console.print(c + ("  (default)" if c == settings.get("city") else ""), markup=False)
        if not cities(settings):
            console.print("[dim]No saved cities. Add one: weather add London[/dim]")
        return
    if sub == "add" and len(words) > 1:
        city = " ".join(words[1:])
        settings.setdefault("cities", [])
        if city not in settings["cities"]:
            settings["cities"].append(city)
        settings.setdefault("city", city)
        save(settings)
        console.print(f"[green]Saved {escape(city)}.[/green]")
        return
    if sub == "remove" and len(words) > 1:
        city = " ".join(words[1:])
        settings["cities"] = [c for c in settings.get("cities", []) if c.lower() != city.lower()]
        if settings.get("city", "").lower() == city.lower():
            settings["city"] = (settings["cities"] or [""])[0]
        save(settings)
        console.print("[green]Removed.[/green]")
        return
    if sub == "all":
        for c in cities(settings):
            data, age, error = get_forecast(c, settings, max_age=CACHE_MAX_AGE)
            if data is None:
                console.print(f"{escape(c)}: [red]no data[/red]")
                continue
            warn = " [bold red](warning)[/bold red]" if alerts(data) else ""
            console.print(escape(short_line(data, settings.get("units") == "imperial", c)) + warn + (f"  [dim](saved {int(age // 60)} min ago)[/dim]" if age > 3600 else ""))
        if not cities(settings):
            console.print("[dim]No saved cities. Add one: weather add London[/dim]")
        return
    hourly = sub in ("hourly", "hours")
    city = " ".join(words[1:] if hourly else words) or settings.get("city") or Prompt.ask("City", default="London").strip()
    if not city:
        return
    if show(city, settings, "hourly" if hourly else "current"):
        settings["city"] = city
        save(settings)
    while not args:
        choice = Prompt.ask("(c)ity  (h)ourly  (u)nits  (s)ave this city  (a)ll saved  (r)efresh  (q)uit", choices=["c", "h", "u", "s", "a", "r", "q"], default="q")
        if choice == "q":
            return
        if choice == "u":
            settings["units"] = "metric" if settings.get("units") == "imperial" else "imperial"
            save(settings)
        elif choice == "c":
            city = Prompt.ask("City", default=city).strip() or city
        elif choice == "s":
            settings.setdefault("cities", [])
            if city not in settings["cities"]:
                settings["cities"].append(city)
            save(settings)
            console.print("[green]Saved.[/green]")
            continue
        elif choice == "a":
            main(["all"])
            continue
        show(city, settings, "hourly" if choice == "h" else "current")


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
