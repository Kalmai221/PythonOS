#!/usr/bin/env python3
"""Number guessing with hints: the computer thinks of a number, you guess it. Each wrong guess tells you higher or lower, and 'hint'
shows how close you are (warm/cold) and narrows the range. Try to beat the best possible score: log2(range) guesses."""
import math
import random
import sys

from rich.console import Console

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
LEVELS = {"easy": 50, "medium": 100, "hard": 1000, "expert": 100000}


def temperature(distance, span):
    """Warm/cold wording for how far a guess was, compared with the size of the range."""
    ratio = distance / span
    if ratio <= 0.02:
        return "[bold red]burning hot[/bold red]"
    if ratio <= 0.08:
        return "[red]hot[/red]"
    if ratio <= 0.2:
        return "[yellow]warm[/yellow]"
    if ratio <= 0.4:
        return "[cyan]cool[/cyan]"
    return "[blue]cold[/blue]"


def best_possible(top):
    return math.ceil(math.log2(top))


def play(level, rng=None):
    rng = rng or random.Random()
    top = LEVELS[level]
    secret = rng.randint(1, top)
    low, high = 1, top
    guesses = 0
    console.print(f"[bold]I am thinking of a number from 1 to {top}.[/bold] ({'hint' } for a clue, q to give up) "
                  f"A perfect player needs at most {best_possible(top)} guesses.")
    while True:
        try:
            text = input(f"Guess {guesses + 1}> ").strip().lower()
        except EOFError:
            return None
        if text in ("q", "quit"):
            console.print(f"It was {secret}.")
            return False
        if text == "hint":
            mid = (low + high) // 2
            console.print(f"[dim]It is between {low} and {high}. Guessing {mid} (the middle) is the smartest next move.[/dim]")
            continue
        if not text.lstrip("-").isdigit():
            console.print("[yellow]Type a whole number, or 'hint'.[/yellow]")
            continue
        n = int(text)
        if not 1 <= n <= top:
            console.print(f"[yellow]Between 1 and {top}, please.[/yellow]")
            continue
        guesses += 1
        if n == secret:
            rating = "perfect!" if guesses <= best_possible(top) else "good" if guesses <= best_possible(top) + 2 else "keep practising"
            console.print(f"[bold green]Yes, {secret}! {guesses} guess(es) - {rating}[/bold green]")
            return guesses
        if n < secret:
            low = max(low, n + 1)
        else:
            high = min(high, n - 1)
        console.print(f"{'Higher' if n < secret else 'Lower'}. It is {temperature(abs(n - secret), top)}.")


def main():
    best = appdata.load("guess", {}) if appdata else {}
    while True:
        level = input(f"Level: {', '.join(LEVELS)} (q to quit)> ").strip().lower() or "medium"
        if level == "q":
            return
        if level not in LEVELS:
            continue
        result = play(level)
        if result is None:
            return
        if result and appdata and (level not in best or result < best[level]):
            best[level] = result
            appdata.save("guess", best)
            console.print(f"[yellow]New best for {level}![/yellow]")
        if input("Again? [y/N] ").strip().lower() != "y":
            return


def execute(args=None):
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
