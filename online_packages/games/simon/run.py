#!/usr/bin/env python3
"""Simon: watch the colours light up one by one, then type them back. Every round adds one more.

    simon                 four colours: r g b y
    simon --hard          the pattern is shown faster
    simon --six           six colours (adds o and p)
Type the letters in order, with or without spaces (for example: r g g b). q quits. The pattern is cleared from the screen before you type.
"""
import random
import sys
import time

from rich.console import Console

console = Console()
COLOURS = {"r": ("red", "bold white on red"), "g": ("green", "bold black on green"), "b": ("blue", "bold white on blue"), "y": ("yellow", "bold black on yellow"),
           "o": ("orange", "bold black on dark_orange"), "p": ("purple", "bold white on purple")}


def extend(sequence, letters, rng=random):
    """The pattern with one more colour."""
    return sequence + [rng.choice(letters)]


def check(sequence, answer):
    """(correct?, how many were right in a row) for what the person typed."""
    typed = [c for c in answer.lower() if c in COLOURS]
    right = 0
    for want, got in zip(sequence, typed):
        if want != got:
            break
        right += 1
    return typed == sequence, right


def score(rounds):
    """Points for reaching a round: 10 for each colour remembered, with a growing bonus."""
    return sum(10 + 2 * n for n in range(rounds))


def play(letters, delay, rng=random, sleep=time.sleep):
    sequence, completed = [], 0
    while True:
        sequence = extend(sequence, letters, rng)
        console.print(f"\n[bold]Round {len(sequence)}[/bold] - watch...")
        sleep(0.8)
        for letter in sequence:
            name, style = COLOURS[letter]
            console.print(f"  [{style}]  {name.upper():^8}  [/{style}]", end="\r")
            sleep(delay)
            console.print(" " * 24, end="\r")
            sleep(delay / 3)
        console.clear()
        try:
            answer = console.input(f"[bold]Your turn[/bold] ({len(sequence)} colours, letters {' '.join(letters)}, q quits): ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            return completed
        if answer.lower() == "q":
            return completed
        good, right = check(sequence, answer)
        if not good:
            shown = " ".join(f"[{COLOURS[c][1]}] {c} [/{COLOURS[c][1]}]" for c in sequence)
            console.print(f"[red]Not quite[/red] - you got {right} right. It was: {shown}")
            return completed
        completed += 1
        console.print("[green]Right![/green]")


def main(argv):
    letters = list("rgbyop") if "--six" in argv else list("rgby")
    delay = 0.35 if "--hard" in argv else 0.7
    console.print("[bold]Simon[/bold] - " + " ".join(f"[{COLOURS[c][1]}] {c} [/{COLOURS[c][1]}]" for c in letters))
    completed = play(letters, delay)
    console.print(f"\nYou remembered {completed} round(s): [bold]{score(completed)} points[/bold].")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
