#!/usr/bin/env python3
"""ISS tracker: where the International Space Station is right now (api.wheretheiss.at, no account or key).

    iss                  the position, height and speed
    iss --watch 5        read it 5 times, 10 seconds apart (Ctrl+C stops)
"""
import sys
import time

import requests
from rich.console import Console
from rich.markup import escape

console = Console()
URL = "https://api.wheretheiss.at/v1/satellites/25544"
HEADERS = {"User-Agent": "PythonOS-iss/1.0 (https://github.com/Kalmai221/PythonOS)"}


def fetch():
    response = requests.get(URL, timeout=10, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def hemisphere(value, positive, negative):
    return f"{abs(value):.2f}° {positive if value >= 0 else negative}"


def describe(data):
    """Lines of text for one reading of the service."""
    lat, lon = float(data["latitude"]), float(data["longitude"])
    kmh = float(data.get("velocity", 0))
    lines = [
        f"Position   {hemisphere(lat, 'N', 'S')}, {hemisphere(lon, 'E', 'W')}",
        f"Height     {float(data.get('altitude', 0)):.0f} km above the Earth",
        f"Speed      {kmh:,.0f} km/h  ({kmh / 3600:.1f} km every second)",
    ]
    visibility = data.get("visibility")
    if visibility:
        lines.append("Light      " + {"daylight": "in daylight", "visible": "in the dark, a ground observer could see it", "eclipsed": "in the Earth's shadow"}.get(visibility, visibility))
    if data.get("timestamp"):
        lines.append("Reading    " + time.strftime("%H:%M:%S", time.localtime(int(data["timestamp"]))))
    return lines


def main(argv):
    times = 1
    if "--watch" in argv:
        try:
            times = max(1, min(int(argv[argv.index("--watch") + 1]), 60))
        except (IndexError, ValueError):
            console.print(__doc__)
            return 1
    try:
        for n in range(times):
            if n:
                time.sleep(10)
            for line in describe(fetch()):
                console.print(escape(line))
            if n + 1 < times:
                console.print()
    except KeyboardInterrupt:
        return 0
    except (requests.RequestException, ValueError, KeyError) as e:
        console.print(f"[red]Could not read the ISS position ({escape(type(e).__name__)}). Check the internet connection.[/red]")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
