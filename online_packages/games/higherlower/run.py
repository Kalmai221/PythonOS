#!/usr/bin/env python3
"""Higher or lower: a card is shown, guess whether the next one is higher or lower. How long a streak can you build?

    higherlower              one 52-card deck, aces high
    higherlower --jokers     two jokers in the deck as well: a joker is always a wrong guess

Type h (higher), l (lower) or q (quit). The same value as the card shown is a draw: the streak goes on and the card changes.
"""
import random
import sys

from rich.console import Console

console = Console()
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = ["♠", "♥", "♦", "♣"]
RED = {"♥", "♦"}


def new_deck(rng=random, jokers=False):
    deck = [(r, s) for r in RANKS for s in SUITS]
    if jokers:
        deck += [("*", "joker"), ("*", "joker")]
    rng.shuffle(deck)
    return deck


def value(card):
    """The card's rank as a number (2 to 14); a joker is None."""
    return RANKS.index(card[0]) + 2 if card[0] in RANKS else None


def judge(current, following, guess):
    """'win', 'lose' or 'draw' for a guess ('h' or 'l') about the next card."""
    a, b = value(current), value(following)
    if b is None:
        return "lose"
    if a == b:
        return "draw"
    return "win" if (b > a) == (guess == "h") else "lose"


def show(card):
    if card[0] == "*":
        return "[bold magenta]JOKER[/bold magenta]"
    colour = "red" if card[1] in RED else "white"
    return f"[bold {colour}]{card[0]}{card[1]}[/bold {colour}]"


def odds(current, remaining):
    """(chance of higher, chance of lower) as percentages, from the cards still in the deck."""
    known = [value(c) for c in remaining if value(c) is not None]
    if not known:
        return 0, 0
    a = value(current)
    return round(100 * sum(1 for v in known if v > a) / len(known)), round(100 * sum(1 for v in known if v < a) / len(known))


def main(argv):
    deck = new_deck(jokers="--jokers" in argv)
    current = deck.pop()
    while current[0] == "*" and deck:
        current = deck.pop()
    streak = best = 0
    console.print("[bold]Higher or lower[/bold]  - h, l or q")
    while deck:
        high, low = odds(current, deck)
        console.print(f"\nCard: {show(current)}   [dim]streak {streak}, best {best}, {len(deck)} cards left (higher {high}%, lower {low}%)[/dim]")
        try:
            guess = console.input("[bold]higher or lower?[/bold] (h/l/q) ").strip().lower()[:1]
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if guess == "q":
            break
        if guess not in ("h", "l"):
            console.print("[red]Type h for higher, l for lower, or q to stop.[/red]")
            continue
        following = deck.pop()
        outcome = judge(current, following, guess)
        console.print(f"Next: {show(following)}  ->  " + {"win": "[green]right![/green]", "lose": "[red]wrong[/red]", "draw": "[yellow]a draw[/yellow]"}[outcome])
        if outcome == "win":
            streak += 1
            best = max(best, streak)
        elif outcome == "lose":
            streak = 0
        current = following if following[0] != "*" else current
    console.print(f"\n[bold]Best streak: {best}[/bold]" + ("  [green]you went through the whole deck![/green]" if not deck else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
