#!/usr/bin/env python3
"""Emoji: find them by name and convert between :shortcodes: and the pictures (the emoji library, works offline).

    emoji party                       emoji whose name has "party"
    emoji "thumbs up"                 several words must all appear
    emoji --say "Great job :thumbs_up: see you :wave:"     turn :shortcodes: into emoji
    emoji --plain "Great job 👍"                            turn emoji back into :shortcodes:
    emoji --count "Great job 👍👍 and 🎉"                    how many emoji a text has
Whether a picture shows depends on the font of your terminal.
"""
import sys

from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console()


def load():
    try:
        import emoji
    except ImportError:
        console.print("[red]The 'emoji' library is not installed. Install this app again to get it.[/red]")
        sys.exit(1)
    return emoji


def names(entry):
    """The ':names:' an emoji is known by, from one entry of the library's table."""
    found = []
    if isinstance(entry, dict):
        if entry.get("en"):
            found.append(entry["en"])
        found.extend(a for a in entry.get("alias") or [] if a)
    return found


def search(library, words, limit=40):
    """[(emoji, main name)] for emoji whose name contains every word (the plainest names first)."""
    words = [w.lower().replace(" ", "_") for w in words if w]
    if not words:
        return []
    hits = []
    for char, entry in library.EMOJI_DATA.items():
        label = names(entry)
        if not label:
            continue
        text = " ".join(label).lower()
        if all(w in text for w in words):
            hits.append((len(label[0]), label[0].strip(":"), char))
    hits.sort()
    return [(char, name) for _length, name, char in hits[:limit]]


def say(library, text):
    return library.emojize(text, language="alias")


def plain(library, text):
    return library.demojize(text)


def count(library, text):
    """How many emoji a text has."""
    return library.emoji_count(text)


def main(argv):
    argv = list(argv)
    if not argv:
        console.print(__doc__)
        return 1
    library = load()
    mode = argv[0] if argv[0] in ("--say", "--plain", "--count") else None
    rest = argv[1:] if mode else argv
    if mode in ("--say", "--plain", "--count"):
        text = " ".join(rest)
        if not text:
            console.print(__doc__)
            return 1
        if mode == "--say":
            print(say(library, text))
        elif mode == "--plain":
            print(plain(library, text))
        else:
            console.print(f"{count(library, text)} emoji")
        return 0
    found = search(library, rest)
    if not found:
        console.print("No emoji with that name. Try one word, like: emoji cat")
        return 0
    table = Table(show_header=False, box=None)
    table.add_column()
    table.add_column(style="dim")
    for char, name in found:
        table.add_row(Text(char), Text(":" + name + ":"))          # (Text: Rich would turn the :shortcode: back into the picture)
    console.print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
