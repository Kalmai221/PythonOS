#!/usr/bin/env python3
"""Countries: facts about a country (restcountries.com, no account or key).

    countries japan                  capital, people, size, languages, money, calling code, time zones
    countries "united" --list        every country with that in its name
    countries de                     a two-letter code works too (also ISO three-letter: deu)
    countries --region europe        all countries of a region, biggest first (africa, americas, asia, europe, oceania)
"""
import sys
import urllib.parse

import requests
from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()
BASE = "https://restcountries.com/v3.1/"
HEADERS = {"User-Agent": "PythonOS-countries/1.0 (https://github.com/Kalmai221/PythonOS)"}
FIELDS = "name,cca2,cca3,capital,region,subregion,population,area,languages,currencies,idd,timezones,borders,flag,tld,continents"
REGIONS = ("africa", "americas", "asia", "europe", "oceania")


def get(path, **params):
    response = requests.get(BASE + path, params=params, timeout=12, headers=HEADERS)
    if response.status_code == 404:
        return []
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else []


def find(query):
    """The countries that match a name or a code, best match first."""
    text = urllib.parse.quote(query.strip(), safe="")
    if len(query.strip()) in (2, 3) and query.strip().isalpha():
        by_code = get("alpha/" + text, fields=FIELDS)
        if by_code:
            return by_code
    exact = get("name/" + text, fullText="true", fields=FIELDS)
    return exact or get("name/" + text, fields=FIELDS)


def calling_code(country):
    idd = country.get("idd") or {}
    root, suffixes = idd.get("root") or "", idd.get("suffixes") or []
    if not root:
        return ""
    return root + (suffixes[0] if len(suffixes) == 1 else "")


def describe(country):
    """[(label, value)] rows for one country."""
    name = country.get("name") or {}
    currencies = ", ".join(f"{c.get('name', code)} ({c.get('symbol', code)})" if isinstance(c, dict) else code for code, c in (country.get("currencies") or {}).items())
    area, population = country.get("area") or 0, country.get("population") or 0
    rows = [("Name", f"{name.get('common', '?')} ({name.get('official', '')})".replace(" ()", "")),
            ("Codes", f"{country.get('cca2', '')} / {country.get('cca3', '')}"),
            ("Capital", ", ".join(country.get("capital") or []) or "none"),
            ("Region", ", ".join(x for x in (country.get("region"), country.get("subregion")) if x)),
            ("People", f"{population:,}"), ("Area", f"{area:,.0f} km2" + (f"  ({population / area:,.0f} people per km2)" if area else "")),
            ("Languages", ", ".join((country.get("languages") or {}).values()) or "?"), ("Money", currencies or "?")]
    code = calling_code(country)
    if code:
        rows.append(("Calling code", code))
    if country.get("tld"):
        rows.append(("Internet domain", ", ".join(country["tld"])))
    zones = country.get("timezones") or []
    if zones:
        rows.append(("Time zones", ", ".join(zones[:6]) + (f" and {len(zones) - 6} more" if len(zones) > 6 else "")))
    if country.get("borders"):
        rows.append(("Borders", ", ".join(country["borders"])))
    return rows


def main(argv):
    argv = list(argv)
    region = None
    if "--region" in argv:
        i = argv.index("--region")
        region = (argv[i + 1].lower() if i + 1 < len(argv) else "")
        del argv[i:i + 2]
        if region not in REGIONS:
            console.print(__doc__)
            console.print("[red]The regions are: " + ", ".join(REGIONS) + ".[/red]")
            return 1
    show_list = "--list" in argv
    argv = [a for a in argv if a != "--list"]
    query = " ".join(argv).strip()
    if not query and not region:
        console.print(__doc__)
        return 1
    try:
        if region:
            found = sorted(get("region/" + region, fields="name,cca2,capital,population,area"), key=lambda c: -(c.get("population") or 0))
            show_list = True
        else:
            found = find(query)
    except (requests.RequestException, ValueError) as e:
        console.print(f"[red]Could not reach the country service ({escape(type(e).__name__)}). Check the internet connection.[/red]")
        return 1
    if not found:
        console.print(f"[red]No country matches '{escape(query)}'.[/red]")
        return 1
    if len(found) > 1 and not show_list:
        exact = [c for c in found if (c.get("name") or {}).get("common", "").lower() == query.lower()]
        if exact:
            found = exact
        else:
            show_list = True
    if show_list:
        table = Table(title=f"{len(found)} countries")
        for column, justify in (("Country", "left"), ("Code", "left"), ("Capital", "left"), ("People", "right"), ("Area km2", "right")):
            table.add_column(column, justify=justify)
        for c in found[:60]:
            table.add_row(escape((c.get("name") or {}).get("common", "?")), c.get("cca2", ""), escape(", ".join(c.get("capital") or [])),
                          f"{c.get('population') or 0:,}", f"{c.get('area') or 0:,.0f}")
        console.print(table)
        if len(found) > 60:
            console.print(f"[dim]{len(found) - 60} more not shown.[/dim]")
        return 0
    for label, value in describe(found[0]):
        console.print(f"[dim]{label:16}[/dim] {escape(value)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
