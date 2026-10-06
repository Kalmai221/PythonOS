#!/usr/bin/env python3
"""Dictionary: what a word means.

    define serendipity
    define run -n 5          up to 5 meanings of each kind
"""
import sys

import requests
from rich.console import Console
from rich.markup import escape

console = Console()
URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"


def lookup(word):
    """The entries for a word (a list of dicts), or None when the dictionary has no such word."""
    response = requests.get(URL + requests.utils.quote(word.strip().lower()), timeout=10, headers={"User-Agent": "PythonOS-define/1.0"})
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else None


def flatten(entries, limit=3):
    """[(part of speech, [(definition, example)], [synonyms])] from the entries, at most `limit` meanings of each kind."""
    kinds = {}
    for entry in entries:
        for meaning in entry.get("meanings", []):
            kind = meaning.get("partOfSpeech", "")
            slot = kinds.setdefault(kind, {"defs": [], "syn": []})
            slot["syn"] += [s for s in meaning.get("synonyms", []) if s not in slot["syn"]]
            for d in meaning.get("definitions", []):
                if len(slot["defs"]) < limit and d.get("definition"):
                    slot["defs"].append((d["definition"], d.get("example", "")))
    return [(kind, slot["defs"], slot["syn"][:8]) for kind, slot in kinds.items() if slot["defs"]]


def phonetic(entries):
    for entry in entries:
        if entry.get("phonetic"):
            return entry["phonetic"]
        for p in entry.get("phonetics", []):
            if p.get("text"):
                return p["text"]
    return ""


def execute(args=None):
    args = list(args or [])
    limit = 3
    if "-n" in args:
        i = args.index("-n")
        if i + 1 < len(args) and args[i + 1].isdigit():
            limit = max(1, min(10, int(args[i + 1])))
            del args[i:i + 2]
    if len(args) != 1:
        console.print("[bold red]Usage:[/bold red] define <word>   (one word; -n 5 for more meanings)")
        return False
    word = args[0]
    try:
        entries = lookup(word)
    except requests.RequestException as e:
        console.print(f"[bold red]define: could not reach the dictionary ({escape(str(e)[:80])})[/bold red]")
        return False
    if not entries:
        console.print(f"[yellow]No definition for '{escape(word)}'. Check the spelling.[/yellow]")
        return False
    console.print(f"[bold]{escape(word)}[/bold]  [dim]{escape(phonetic(entries))}[/dim]")
    for kind, defs, synonyms in flatten(entries, limit):
        console.print(f"\n[italic]{escape(kind)}[/italic]")
        for number, (definition, example) in enumerate(defs, 1):
            console.print(f"  {number}. {escape(definition)}")
            if example:
                console.print(f"     [dim]\"{escape(example)}\"[/dim]")
        if synonyms:
            console.print(f"  [dim]Also: {escape(', '.join(synonyms))}[/dim]")
    return True


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
