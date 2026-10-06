#!/usr/bin/env python3
"""Regex tester: try a regular expression on sample text and see every match, its position and its groups, with the matches highlighted.
Also explains what the pattern does, shows a cheat sheet and can test several lines at once. Patterns that take too long (catastrophic
backtracking) are stopped after a couple of seconds.
Usage: regextest <pattern> <text>  |  regextest  (interactive; commands :flags i m s x, :help, :quit)"""
import re
import signal
import sys
import threading

from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

console = Console()
TIMEOUT = 2.0
MAX_TEXT = 5000
CHEAT = r"""Characters   .  any character   \d digit   \w letter/digit/_   \s space   \b word edge   [abc] one of   [^abc] none of
Repeats      *  0 or more   +  1 or more   ?  optional   {3}  exactly 3   {2,5}  2 to 5   (add ? to be lazy: *?)
Positions    ^  start   $  end   (?=x) followed by x   (?!x) not followed by x
Groups       (abc) capture   (?:abc) no capture   (?P<name>abc) named   a|b  a or b
Flags        i ignore case   m ^ and $ per line   s dot matches newline   x allow spaces and # comments"""
FLAG_BITS = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL, "x": re.VERBOSE}
TOKENS = [(r"\\d", "a digit"), (r"\\D", "a non-digit"), (r"\\w", "a letter, digit or _"), (r"\\W", "not a letter, digit or _"),
          (r"\\s", "a space or tab"), (r"\\S", "not a space"), (r"\\b", "a word boundary"), (r"\.", "any character"),
          (r"\^", "the start"), (r"\$", "the end"), (r"\*\?", "lazily, 0 or more"), (r"\+\?", "lazily, 1 or more"),
          (r"\*", "0 or more of the last thing"), (r"\+", "1 or more of the last thing"), (r"\?", "optional"),
          (r"\{\d+,?\d*\}", "a repeat count"), (r"\[\^?[^\]]*\]", "a character set"), (r"\(\?P<\w+>", "start of a named group"),
          (r"\(\?:", "start of a non-capturing group"), (r"\(\?[=!]", "a look-ahead"), (r"\(", "start of a group"), (r"\)", "end of a group"),
          (r"\|", "or")]


def flags_from(letters):
    value = 0
    for ch in letters:
        value |= FLAG_BITS.get(ch, 0)
    return value


def risky(pattern):
    """True for patterns that are likely to backtrack catastrophically: a repeated group that itself repeats or has alternatives
    ("(a+)+", "(a*)*", "(a|aa)+"). Python's regex engine holds the interpreter while it matches, so it cannot be stopped from another
    thread; where a timer signal is not available (Windows) such patterns are refused instead."""
    return bool(re.search(r"\((?:\?:)?[^()]*(?:[*+]|\{\d*,\d*\})[^()]*\)\s*(?:[*+]|\{\d*,\d*\})", pattern)
                or re.search(r"\((?:\?:)?[^()|]*\|[^()]*\)\s*(?:[*+]|\{\d*,\d*\})", pattern))


def run_with_timeout(func, seconds=TIMEOUT, pattern=""):
    """Run func(). On Linux and macOS an interval timer interrupts a pattern that runs too long; elsewhere risky patterns are refused."""
    message = "That pattern took too long (it may backtrack catastrophically). Try making it simpler."
    if hasattr(signal, "setitimer") and threading.current_thread() is threading.main_thread():
        def handler(signum, frame):
            raise TimeoutError(message)
        old = signal.signal(signal.SIGALRM, handler)
        signal.setitimer(signal.ITIMER_REAL, seconds)
        try:
            return func()
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)
    if pattern and risky(pattern):
        raise TimeoutError("That pattern repeats a repeating group, which can freeze the matcher on some text. Rewrite it more simply "
                           "(for example (a+)+ can usually be written a+).")
    return func()


def find_all(pattern, text, flags=0, limit=200):
    """[(start, end, text, groups, groupdict)] for every non-overlapping match."""
    rx = re.compile(pattern, flags)
    out = []
    for m in rx.finditer(text):
        out.append((m.start(), m.end(), m.group(0), m.groups(), m.groupdict()))
        if len(out) >= limit:
            break
    return out


def highlight(text, matches):
    out = Text()
    pos = 0
    colours = ["black on yellow", "black on green", "black on cyan"]
    for i, (start, end, *_rest) in enumerate(matches):
        if start < pos:
            continue
        out.append(text[pos:start])
        out.append(text[start:end] or "|", style=colours[i % len(colours)])
        pos = end
    out.append(text[pos:])
    return out


def explain(pattern):
    """Plain-English notes on the parts of a pattern (best effort for common syntax)."""
    notes, i = [], 0
    while i < len(pattern):
        for token, meaning in TOKENS:
            m = re.match(token, pattern[i:])
            if m and m.group(0):
                notes.append((m.group(0), meaning))
                i += len(m.group(0))
                break
        else:
            j = i
            while j < len(pattern) and not re.match("|".join(t for t, _ in TOKENS), pattern[j:]):
                j += 1
            literal = pattern[i:max(j, i + 1)]
            notes.append((literal, "the text " + repr(literal)))
            i += len(literal)
    return notes


def test(pattern, text, flags=0):
    try:
        matches = run_with_timeout(lambda: find_all(pattern, text[:MAX_TEXT], flags), pattern=pattern)
    except re.error as e:
        console.print(f"[red]Not a valid pattern: {escape(str(e))}[/red]")
        return None
    except TimeoutError as e:
        console.print(f"[red]{e}[/red]")
        return None
    if not matches:
        console.print("[yellow]No match.[/yellow]")
        return matches
    console.print(highlight(text, matches))
    table = Table(header_style="bold blue")
    for col in ("#", "Match", "Position", "Groups"):
        table.add_column(col)
    for i, (s, e, t, groups, named) in enumerate(matches[:30], 1):
        shown = ", ".join(f"{k}={v!r}" for k, v in named.items()) if named else ", ".join(repr(g) for g in groups)
        table.add_row(str(i), escape(t) or "(empty)", f"{s}-{e}", escape(shown))
    console.print(table)
    console.print(f"[green]{len(matches)} match(es)[/green]")
    return matches


def main(args):
    if len(args) >= 2:
        test(args[0], " ".join(args[1:]))
        return
    flags_letters = ""
    console.print("[bold]Regex tester[/bold]  :flags i m s x   :explain   :help   :quit")
    pattern = ""
    while True:
        text = Prompt.ask("[cyan]pattern[/cyan]" + (f" [dim]({pattern})[/dim]" if pattern else ""), default=pattern, show_default=False)
        if text in (":quit", ":q"):
            return
        if text == ":help":
            console.print(CHEAT, markup=False, highlight=False)
            continue
        if text.startswith(":flags"):
            flags_letters = text[6:].strip().replace(" ", "")
            console.print(f"[dim]flags: {flags_letters or 'none'}[/dim]")
            continue
        if text == ":explain":
            for token, meaning in explain(pattern):
                console.print(f"  [bold]{escape(token)}[/bold]  {escape(meaning)}")
            continue
        pattern = text
        console.print("[dim]Type sample text, one line at a time; blank to change the pattern.[/dim]")
        while True:
            sample = Prompt.ask("[cyan]text[/cyan]", default="", show_default=False)
            if not sample:
                break
            test(pattern, sample, flags_from(flags_letters))


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
