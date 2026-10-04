#!/usr/bin/env python3
import json
import os
import requests
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()


def settings_file():
    try:
        with open("current_user.json") as f:
            user = json.load(f)["username"]
    except Exception:
        user = None
    folder = os.path.join("files", "home", user) if user else "files"
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, ".weather.json")


def load_city():
    try:
        with open(settings_file()) as f:
            return json.load(f).get("city", "")
    except (OSError, ValueError):
        return ""


def save_city(city):
    with open(settings_file(), "w") as f:
        json.dump({"city": city}, f)


def main():
    saved = load_city()
    city = Prompt.ask("City", default=saved or "London").strip()
    if not city:
        return
    try:
        with console.status("Fetching weather..."):
            response = requests.get(f"https://wttr.in/{requests.utils.quote(city)}?format=j1", timeout=10)
            response.raise_for_status()
            data = response.json()
        now = data["current_condition"][0]
        area = data["nearest_area"][0]
        place = f"{area['areaName'][0]['value']}, {area['country'][0]['value']}"
        body = (f"[bold]{now['weatherDesc'][0]['value']}[/bold]\n\n"
                f"Temperature : {now['temp_C']} C (feels like {now['FeelsLikeC']} C)\n"
                f"Humidity    : {now['humidity']}%\n"
                f"Wind        : {now['windspeedKmph']} km/h {now['winddir16Point']}\n"
                f"Visibility  : {now['visibility']} km")
        console.print(Panel(body, title=f"[bold cyan]{place}[/bold cyan]", border_style="blue", expand=False))
        save_city(city)
    except requests.RequestException:
        console.print("[bold red]Could not reach the weather service. Check your internet connection.[/bold red]")
    except (KeyError, IndexError, ValueError):
        console.print(f"[bold red]No weather found for '{city}'.[/bold red]")


if __name__ == "__main__":
    main()


def execute():
    main()
