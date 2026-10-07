#!/usr/bin/env python3
"""Rock, paper, scissors, lizard, Spock - against a computer that studies how you play.

    rps              best of as many rounds as you like
    rps classic      only rock, paper, scissors

Type r, p, s, l or k (Spock) - or the full word. q ends the game and shows the score.
The computer remembers what you played after each of your last moves and bets on the pattern; it only works if you have habits.
"""
import random
import sys

from rich.console import Console

console = Console()
FULL = {"rock": ("scissors", "lizard"), "paper": ("rock", "spock"), "scissors": ("paper", "lizard"), "lizard": ("paper", "spock"),
        "spock": ("rock", "scissors")}
KEYS = {"r": "rock", "p": "paper", "s": "scissors", "l": "lizard", "k": "spock"}
VERB = {("rock", "scissors"): "crushes", ("rock", "lizard"): "crushes", ("paper", "rock"): "covers", ("paper", "spock"): "disproves",
        ("scissors", "paper"): "cuts", ("scissors", "lizard"): "decapitates", ("lizard", "paper"): "eats", ("lizard", "spock"): "poisons",
        ("spock", "rock"): "vaporises", ("spock", "scissors"): "smashes"}


def outcome(a, b):
    """1 if a beats b, -1 if b beats a, 0 for a tie."""
    if a == b:
        return 0
    return 1 if b in FULL[a] else -1


def counter_to(move, choices):
    """A move from `choices` that beats `move`."""
    return random.choice([c for c in choices if move in FULL[c]])


class Predictor:
    """Remembers which move followed which: after rock you tend to play X. Bets on the most likely next move."""

    def __init__(self):
        self.after = {}
        self.last = None

    def learn(self, move):
        if self.last is not None:
            table = self.after.setdefault(self.last, {})
            table[move] = table.get(move, 0) + 1
        self.last = move

    def guess(self, choices, rng=None):
        rng = rng or random
        table = self.after.get(self.last)
        if not table or sum(table.values()) < 2:
            return rng.choice(choices)
        top = max(table.values())
        likely = rng.choice([m for m, n in table.items() if n == top])
        return rng.choice([c for c in choices if likely in FULL[c]] or choices)


def main(argv):
    choices = ["rock", "paper", "scissors"] if argv and argv[0].lower() == "classic" else list(FULL)
    keys = {k: v for k, v in KEYS.items() if v in choices}
    brain, wins, losses, ties = Predictor(), 0, 0, 0
    console.print("[bold]Rock, paper, scissors" + ("" if len(choices) == 3 else ", lizard, Spock") + "[/bold]   type " + ", ".join(f"{k}={v}" for k, v in keys.items()) + ", q to stop")
    while True:
        try:
            line = console.input("[bold]your move> [/bold]").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if line in ("q", "quit"):
            break
        mine = keys.get(line, line if line in choices else None)
        if mine is None:
            console.print("[red]Not a move.[/red]")
            continue
        theirs = brain.guess(choices)
        brain.learn(mine)
        result = outcome(mine, theirs)
        if result == 0:
            ties += 1
            console.print(f"Both chose {mine}: a tie.")
        elif result == 1:
            wins += 1
            console.print(f"[green]{mine.capitalize()} {VERB.get((mine, theirs), 'beats')} {theirs}. You win![/green]")
        else:
            losses += 1
            console.print(f"[red]{theirs.capitalize()} {VERB.get((theirs, mine), 'beats')} {mine}. The computer wins.[/red]")
    total = wins + losses + ties
    if total:
        console.print(f"\nYou won {wins}, the computer won {losses}, {ties} ties ({wins * 100 // total}% for you).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
