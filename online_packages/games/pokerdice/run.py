#!/usr/bin/env python3
"""Poker dice: roll five dice up to three times, keeping the ones you like, and make the best poker hand you can. Hands, best first:
five of a kind, four of a kind, full house, straight, three of a kind, two pair, one pair, high die. Play against the computer.
After a roll type the numbers of the dice to KEEP (like 1 3 4), 'all' to keep everything, or Enter to roll them all again."""
import random
import sys
from collections import Counter

from rich.console import Console
from rich.text import Text

console = Console()
FACES = {1: "9", 2: "10", 3: "J", 4: "Q", 5: "K", 6: "A"}
NAMES = ["High die", "One pair", "Two pair", "Three of a kind", "Straight", "Full house", "Four of a kind", "Five of a kind"]


def rank(dice):
    """(hand level 0-7, tiebreak tuple) - bigger is better."""
    counts = Counter(dice)
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], -kv[0]))
    shape = [n for _, n in ordered]
    tiebreak = tuple(v for v, _ in ordered)
    if shape == [5]:
        return 7, tiebreak
    if shape == [4, 1]:
        return 6, tiebreak
    if shape == [3, 2]:
        return 5, tiebreak
    if sorted(dice) in ([1, 2, 3, 4, 5], [2, 3, 4, 5, 6]):
        return 4, (max(dice),)
    if shape == [3, 1, 1]:
        return 3, tiebreak
    if shape == [2, 2, 1]:
        return 2, tiebreak
    if shape == [2, 1, 1, 1]:
        return 1, tiebreak
    return 0, tuple(sorted(dice, reverse=True))


def describe(dice):
    level, _ = rank(dice)
    return NAMES[level]


def show(dice, keep=()):
    out = Text()
    for i, d in enumerate(dice, 1):
        out.append(f" {i}:{FACES[d]} ", style="bold green" if i in keep else "bold white")
    return out


def computer_keep(dice):
    """Keep the dice that belong to the most common value; a straight is kept whole; otherwise keep the high dice."""
    counts = Counter(dice)
    value, n = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
    if n >= 2:
        return [i for i, d in enumerate(dice) if d == value]
    if rank(dice)[0] == 4:
        return list(range(5))
    return [i for i, d in enumerate(dice) if d >= 5]


def roll(dice, keep, rng):
    return [d if i in keep else rng.randint(1, 6) for i, d in enumerate(dice)]


def player_turn(rng):
    dice = [rng.randint(1, 6) for _ in range(5)]
    for attempt in (1, 2, 3):
        console.print(Text(f"Roll {attempt}: ") + show(dice) + Text(f"  -> {describe(dice)}", style="dim"))
        if attempt == 3:
            break
        try:
            text = input("Keep which dice? (numbers, 'all', Enter = roll all)> ").strip().lower()
        except EOFError:
            return None
        if text in ("q", "quit"):
            return None
        if text == "all":
            break
        keep = {int(t) - 1 for t in text.replace(",", " ").split() if t.isdigit() and 1 <= int(t) <= 5}
        dice = roll(dice, keep, rng)
    return dice


def computer_turn(rng):
    dice = [rng.randint(1, 6) for _ in range(5)]
    for _ in range(2):
        dice = roll(dice, set(computer_keep(dice)), rng)
    return dice


def play(rng=None):
    rng = rng or random.Random()
    mine = player_turn(rng)
    if mine is None:
        return None
    theirs = computer_turn(rng)
    console.print(Text("Computer: ") + show(theirs) + Text(f"  -> {describe(theirs)}"))
    a, b = rank(mine), rank(theirs)
    if a > b:
        console.print(f"[bold green]You win with {describe(mine)}![/bold green]")
        return True
    if a < b:
        console.print(f"[bold red]The computer wins with {describe(theirs)}.[/bold red]")
        return False
    console.print("[bold yellow]A tie.[/bold yellow]")
    return 0


def main():
    score = {True: 0, False: 0}
    console.print("[bold]Poker dice[/bold]  (q at any question to quit)")
    while True:
        result = play()
        if result is None:
            return
        if result in score:
            score[result] += 1
        console.print(f"[dim]You {score[True]} - {score[False]} computer[/dim]")
        if input("Another round? [Y/n] ").strip().lower() == "n":
            return


def execute(args=None):
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
