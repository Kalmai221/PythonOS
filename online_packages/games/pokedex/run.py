#!/usr/bin/env python3
"""Pokedex: look up a Pokemon (pokeapi.co, no account or key).

    pokedex pikachu
    pokedex 25                  by Pokedex number
    pokedex mr-mime             names are lower case with dashes
    pokedex random              a surprise
"""
import random
import sys
import textwrap

import requests
from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()
BASE = "https://pokeapi.co/api/v2/"
HEADERS = {"User-Agent": "PythonOS-pokedex/1.0 (https://github.com/Kalmai221/PythonOS)"}
TOTAL = 1025                                                 # Pokedex numbers 1..1025 exist; the service has more forms after that
STAT_NAMES = {"hp": "HP", "attack": "Attack", "defense": "Defense", "special-attack": "Sp. Attack", "special-defense": "Sp. Defense", "speed": "Speed"}


def get(path):
    response = requests.get(BASE + path, timeout=10, headers=HEADERS)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def entry_text(species):
    """The English Pokedex entry of a species, on one line."""
    for item in (species or {}).get("flavor_text_entries", []):
        if (item.get("language") or {}).get("name") == "en":
            return " ".join(item.get("flavor_text", "").replace("\f", " ").split())
    return ""


def describe(pokemon, species=None):
    """A dict with what is shown: name, number, types, abilities, height (m), weight (kg), stats [(name, value)], and the entry."""
    return {
        "name": pokemon["name"], "id": pokemon["id"],
        "types": [t["type"]["name"] for t in pokemon.get("types", [])],
        "abilities": [a["ability"]["name"].replace("-", " ") + (" (hidden)" if a.get("is_hidden") else "") for a in pokemon.get("abilities", [])],
        "height": pokemon.get("height", 0) / 10, "weight": pokemon.get("weight", 0) / 10,
        "stats": [(STAT_NAMES.get(s["stat"]["name"], s["stat"]["name"]), s["base_stat"]) for s in pokemon.get("stats", [])],
        "entry": entry_text(species),
    }


def bar(value, width=20):
    filled = max(0, min(width, round(value / 255 * width)))
    return "█" * filled + "░" * (width - filled)


def main(argv):
    if not argv:
        console.print(__doc__)
        return 1
    query = "-".join(argv).lower().replace(" ", "-")
    if query == "random":
        query = str(random.randint(1, TOTAL))
    try:
        pokemon = get("pokemon/" + query)
        if pokemon is None:
            console.print(f"[red]No Pokemon called '{escape(query)}'. Names are lower case, like mr-mime.[/red]")
            return 1
        species = get("pokemon-species/" + str(pokemon["id"]))
        info = describe(pokemon, species)
    except (requests.RequestException, ValueError, KeyError) as e:
        console.print(f"[red]Could not reach the Pokedex ({escape(type(e).__name__)}). Check the internet connection.[/red]")
        return 1
    console.print(f"[bold]#{info['id']} {escape(info['name'].replace('-', ' ').title())}[/bold]   " + " / ".join(info["types"]))
    if info["entry"]:
        console.print("\n" + escape(textwrap.fill(info["entry"], 70)) + "\n")
    console.print(f"Height {info['height']:g} m   Weight {info['weight']:g} kg   Abilities: {escape(', '.join(info['abilities']))}\n")
    table = Table(show_header=False, box=None)
    table.add_column()
    table.add_column(justify="right")
    table.add_column()
    for name, value in info["stats"]:
        table.add_row(name, str(value), f"[green]{bar(value)}[/green]")
    console.print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
