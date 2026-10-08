#!/usr/bin/env python3
"""Word finder: synonyms, opposites, rhymes and more (api.datamuse.com, no account or key).

    synonyms happy                  words that mean the same
    synonyms happy --opposite       antonyms
    synonyms orange --rhyme         words that rhyme
    synonyms elefant --sounds       words that sound like it (a spelling helper)
    synonyms "ringing in the ears" --means    words for a meaning
    synonyms "te*r" --spelled       words that fit a pattern (* is any letters, ? is one letter)
    synonyms happy -n 40            more results (up to 100)
"""
import sys

import requests
from rich.columns import Columns
from rich.console import Console
from rich.markup import escape

console = Console()
URL = "https://api.datamuse.com/words"
HEADERS = {"User-Agent": "PythonOS-synonyms/1.0 (https://github.com/Kalmai221/PythonOS)"}
MODES = {"--synonyms": ("rel_syn", "Words that mean the same as"), "--opposite": ("rel_ant", "Opposites of"), "--rhyme": ("rel_rhy", "Words that rhyme with"),
         "--sounds": ("sl", "Words that sound like"), "--means": ("ml", "Words that mean"), "--spelled": ("sp", "Words that fit")}


def parse(argv):
    """(parameter, heading, query, count). Raises ValueError."""
    argv, count, mode = list(argv), 25, "--synonyms"
    if "-n" in argv:
        i = argv.index("-n")
        try:
            count = max(1, min(int(argv[i + 1]), 100))
        except (IndexError, ValueError):
            raise ValueError("-n needs a number") from None
        del argv[i:i + 2]
    for flag in MODES:
        if flag in argv:
            mode = flag
            argv.remove(flag)
    query = " ".join(argv).strip()
    if not query:
        raise ValueError("")
    if len(query) > 80:
        raise ValueError("That is too long to look up.")
    parameter, heading = MODES[mode]
    return parameter, heading, query, count


def words(data):
    """The words from the service's answer, best first, without duplicates."""
    seen, found = set(), []
    for entry in data if isinstance(data, list) else []:
        word = entry.get("word") if isinstance(entry, dict) else None
        if word and word not in seen:
            seen.add(word)
            found.append(word)
    return found


def main(argv):
    try:
        parameter, heading, query, count = parse(argv)
    except ValueError as e:
        console.print(__doc__)
        if str(e):
            console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    try:
        response = requests.get(URL, params={parameter: query, "max": count}, timeout=10, headers=HEADERS)
        response.raise_for_status()
        found = words(response.json())
    except (requests.RequestException, ValueError) as e:
        console.print(f"[red]Could not reach the word service ({escape(type(e).__name__)}). Check the internet connection.[/red]")
        return 1
    if not found:
        console.print("Nothing found. Try another word.")
        return 0
    console.print(f"[bold]{escape(heading)} {escape(query)}[/bold]")
    console.print(Columns([escape(w) for w in found], equal=False, column_first=True, padding=(0, 3)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
