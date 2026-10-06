#!/usr/bin/env python3
"""Spell checker (pyspellchecker).

    spell recieve                     check one word and get suggestions
    spell file notes.txt              every unknown word in a file, with its line and suggestions
    spell file notes.txt -l fr        another language (en, es, fr, de, pt, it, ru, ar, nl)
"""
import os
import re
import sys

from rich.console import Console
from rich.markup import escape
from rich.table import Table

try:
    from pyos import fs
except ImportError:                                        # run on its own, outside PythonOS
    fs = None


def resolve(name):
    return fs.resolve(name) if fs else os.path.expanduser(name)

console = Console()
LANGUAGES = ("en", "es", "fr", "de", "pt", "it", "ru", "ar", "nl", "eu", "lv")
WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?", re.UNICODE)
MAX_BYTES = 2_000_000
_checkers = {}


def checker(language="en"):
    from spellchecker import SpellChecker
    if language not in _checkers:
        _checkers[language] = SpellChecker(language=language)
    return _checkers[language]


def words_of(text):
    """[(line number, word)] for every word-like piece of text (numbers, URLs and ALL-CAPS short words are left out)."""
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        line = re.sub(r"https?://\S+|\S+@\S+\.\S+", " ", line)
        for match in WORD.finditer(line):
            word = match.group(0)
            if len(word) > 2 and not (word.isupper() and len(word) <= 5):
                found.append((number, word))
    return found


def check_text(text, language="en"):
    """[(line, word, [suggestions])] for the words the dictionary does not know."""
    spell = checker(language)
    words = words_of(text)
    unknown = spell.unknown([w.replace("’", "'") for _n, w in words])
    out, seen = [], set()
    for number, word in words:
        plain = word.replace("’", "'").lower()
        if plain in unknown and (number, plain) not in seen:
            seen.add((number, plain))
            suggestions = sorted(spell.candidates(plain) or [], key=lambda c: (-spell.word_usage_frequency(c) if hasattr(spell, "word_usage_frequency") else 0, c))
            out.append((number, word, [s for s in suggestions if s != plain][:4]))
    return out


def execute(args=None):
    args = list(args or [])
    language = "en"
    if "-l" in args:
        i = args.index("-l")
        language = args[i + 1] if i + 1 < len(args) else ""
        del args[i:i + 2]
    if language not in LANGUAGES:
        console.print(f"[yellow]Languages: {', '.join(LANGUAGES)}[/yellow]")
        return False
    try:
        import spellchecker  # noqa: F401
    except ImportError:
        console.print("[bold red]spell needs the pyspellchecker library. Install the app again: pkg install spell[/bold red]")
        return False
    if args[:1] == ["file"] and len(args) == 2:
        try:
            path = resolve(args[1])
            if os.path.getsize(path) > MAX_BYTES:
                console.print("[bold red]spell: that file is bigger than 2 MB.[/bold red]")
                return False
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as e:
            console.print(f"[bold red]spell: {escape(args[1])}: {escape(fs.errtext(e) if fs else str(e))}[/bold red]")
            return False
        mistakes = check_text(text, language)
        if not mistakes:
            console.print("[green]No spelling mistakes found.[/green]")
            return True
        table = Table(header_style="bold blue")
        for column in ("Line", "Word", "Maybe"):
            table.add_column(column)
        for number, word, suggestions in mistakes[:200]:
            table.add_row(str(number), word, ", ".join(suggestions) or "-")
        console.print(table)
        console.print(f"[dim]{len(mistakes)} possible mistake(s)" + (" (first 200 shown)" if len(mistakes) > 200 else "") + "[/dim]")
        return False
    if len(args) == 1:
        mistakes = check_text(args[0], language)
        if not mistakes:
            console.print(f"[green]'{escape(args[0])}' looks right.[/green]")
            return True
        console.print(f"[yellow]'{escape(args[0])}' is not in the dictionary.[/yellow] Maybe: {escape(', '.join(mistakes[0][2]) or 'nothing close')}")
        return False
    console.print("[bold red]Usage:[/bold red] spell <word>   or   spell file <path> [-l language]")
    return False


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
