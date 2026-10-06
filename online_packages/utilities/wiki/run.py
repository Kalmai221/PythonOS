#!/usr/bin/env python3
"""Wikipedia: read the summary of an article from the terminal.

    wiki python programming language       the summary of the best match
    wiki -s black holes                    the first search results
    wiki -r                                a random article
    wiki -l de Berlin                      another language edition (en, de, fr, es, ...)
"""
import re
import sys
import textwrap
import urllib.parse

import requests
from rich.console import Console
from rich.markup import escape

console = Console()
HEADERS = {"User-Agent": "PythonOS-wiki/1.0 (https://github.com/Kalmai221/PythonOS)"}


def base(lang):
    return f"https://{lang}.wikipedia.org"


def search(query, lang="en", limit=6):
    """[(title, description)] for a query (the opensearch API)."""
    response = requests.get(base(lang) + "/w/api.php", timeout=10, headers=HEADERS,
                            params={"action": "opensearch", "search": query, "limit": limit, "namespace": 0, "format": "json"})
    response.raise_for_status()
    data = response.json()
    return list(zip(data[1], data[2])) if len(data) >= 3 else []


def summary(title, lang="en"):
    """The summary dict of an article (title, description, extract, url), or None when there is no such article."""
    response = requests.get(base(lang) + "/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_"), safe=""), timeout=10, headers=HEADERS)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    return {"title": data.get("title", title), "description": data.get("description", ""), "extract": data.get("extract", ""),
            "url": (data.get("content_urls", {}).get("desktop", {}) or {}).get("page", ""), "type": data.get("type", "")}


def random_title(lang="en"):
    response = requests.get(base(lang) + "/api/rest_v1/page/random/summary", timeout=10, headers=HEADERS)
    response.raise_for_status()
    return response.json().get("title", "")


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def show(info):
    console.print(f"[bold]{escape(info['title'])}[/bold]" + (f"  [dim]{escape(info['description'])}[/dim]" if info["description"] else ""))
    console.print()
    for line in textwrap.wrap(clean(info["extract"]) or "(no summary)", width=min(console.width, 100) - 2):
        console.print(escape(line))
    if info["url"]:
        console.print(f"\n[dim]{escape(info['url'])}[/dim]")
    if info.get("type") == "disambiguation":
        console.print("[yellow]This is a disambiguation page: the name has several meanings. Try wiki -s <name>.[/yellow]")


def execute(args=None):
    args = list(args or [])
    lang = "en"
    if "-l" in args:
        i = args.index("-l")
        if i + 1 < len(args) and re.fullmatch(r"[a-z]{2,3}", args[i + 1]):
            lang = args[i + 1]
            del args[i:i + 2]
    try:
        if args[:1] == ["-r"]:
            args = [random_title(lang)]
        if args[:1] == ["-s"]:
            found = search(" ".join(args[1:]), lang)
            if not found:
                console.print("[yellow]Nothing found.[/yellow]")
                return False
            for number, (title, description) in enumerate(found, 1):
                console.print(f"{number:>3}. [bold]{escape(title)}[/bold]  [dim]{escape(description[:80])}[/dim]")
            console.print("[dim]Read one with: wiki <title>[/dim]")
            return True
        if not args:
            console.print("[bold red]Usage:[/bold red] wiki <topic>   (wiki -s <words> to search, wiki -r for a random article)")
            return False
        query = " ".join(args)
        info = summary(query, lang)
        if info is None or not info["extract"]:
            found = search(query, lang, 1)
            info = summary(found[0][0], lang) if found else None
        if info is None:
            console.print(f"[yellow]No article for '{escape(query)}'. Try wiki -s {escape(query)}[/yellow]")
            return False
        show(info)
        return True
    except requests.RequestException as e:
        console.print(f"[bold red]wiki: could not reach Wikipedia ({escape(str(e)[:80])})[/bold red]")
        return False


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
