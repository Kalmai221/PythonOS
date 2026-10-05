#!/usr/bin/env python3
"""Mastermind: crack the secret code of four colours in ten tries. After each guess you learn how many pegs are the right colour in
the right place (black) and how many are the right colour in the wrong place (white). Colours: R G B Y O P (red green blue yellow
orange purple). Type a guess like RGBY."""
import random
import sys

from rich.console import Console
from rich.text import Text

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
COLOURS = "RGBYOP"
STYLE = {"R": "red", "G": "green", "B": "blue", "Y": "yellow", "O": "dark_orange", "P": "magenta"}


def score(secret, guess):
    """(black, white): black = right colour and place, white = right colour elsewhere (each peg counted once)."""
    black = sum(s == g for s, g in zip(secret, guess))
    common = sum(min(secret.count(c), guess.count(c)) for c in set(guess))
    return black, common - black


def pegs(code):
    out = Text()
    for ch in code:
        out.append(f" {ch} ", style=f"bold white on {STYLE[ch]}")
        out.append(" ")
    return out


def hint_candidates(history, length=4):
    """All codes consistent with every guess so far (used for hints)."""
    import itertools
    return ["".join(c) for c in itertools.product(COLOURS, repeat=length)
            if all(score("".join(c), g) == s for g, s in history)]


def play(length=4, tries=10, rng=None):
    rng = rng or random.Random()
    secret = "".join(rng.choice(COLOURS) for _ in range(length))
    history = []
    console.print(f"[bold]Mastermind[/bold]: {length} pegs from {', '.join(COLOURS)} (colours can repeat), {tries} tries. "
                  "Black = right colour and place, white = right colour, wrong place. 'hint' gives a possible code, q gives up.")
    while len(history) < tries:
        try:
            guess = input(f"Guess {len(history) + 1}/{tries}> ").strip().upper()
        except EOFError:
            return None
        if guess in ("Q", "QUIT"):
            console.print(Text("The code was ") + pegs(secret))
            return False
        if guess == "HINT":
            possible = hint_candidates(history, length)
            console.print(f"[dim]{len(possible)} code(s) fit your guesses so far, for example {rng.choice(possible)}.[/dim]")
            continue
        if len(guess) != length or any(c not in COLOURS for c in guess):
            console.print(f"[yellow]Type {length} letters from {COLOURS}, like {COLOURS[:length]}.[/yellow]")
            continue
        black, white = score(secret, guess)
        history.append((guess, (black, white)))
        console.print(Text("  ") + pegs(guess) + Text(f"  [black {black}] [white {white}]", style="bold"))
        if black == length:
            console.print(f"[bold green]Cracked it in {len(history)}![/bold green]")
            return len(history)
    console.print(Text("Out of tries. The code was ") + pegs(secret))
    return False


def main():
    stats = appdata.load("mastermind", {"won": 0, "lost": 0, "best": 0}) if appdata else None
    while True:
        result = play()
        if result is None:
            return
        if stats is not None:
            if result:
                stats["won"] += 1
                stats["best"] = result if not stats["best"] else min(stats["best"], result)
            else:
                stats["lost"] += 1
            appdata.save("mastermind", stats)
            console.print(f"[dim]Won {stats['won']}, lost {stats['lost']}, best {stats['best'] or '-'} guesses[/dim]")
        if input("Again? [y/N] ").strip().lower() != "y":
            return


def execute(args=None):
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
