#!/usr/bin/env python3
"""Nim: take turns removing stones from the piles. Whoever takes the last stone wins.

    nim              three piles (3, 4, 5)
    nim misere       the last stone LOSES instead
    nim 1 3 5 7      your own piles

You may take any number of stones, but from one pile only. Type the pile and how many, like: 2 3 (three stones from pile 2).
The computer plays perfectly whenever it can - if you are in a losing position, your best hope is that it makes a "mistake" on purpose
(it does, sometimes, so that you have a chance).
"""
import random
import sys
from functools import reduce

from rich.console import Console

console = Console()


def nim_sum(piles):
    return reduce(lambda a, b: a ^ b, piles, 0)


def best_move(piles, misere=False):
    """(pile index, stones to take) that leaves the opponent in a lost position, or None when every move loses (then any move will do)."""
    big = [i for i, p in enumerate(piles) if p > 1]
    if misere and len(big) <= 1:
        ones = sum(1 for p in piles if p == 1)
        if len(big) == 1:
            i = big[0]
            # leave an odd number of single stones
            return (i, piles[i] - 1) if ones % 2 == 0 else (i, piles[i])
        if ones % 2 == 0 and ones > 0:
            return (piles.index(1), 1)
        return None
    total = nim_sum(piles)
    if total == 0:
        return None
    for i, p in enumerate(piles):
        target = p ^ total
        if target < p:
            return (i, p - target)
    return None


def computer_move(piles, misere=False, rng=None, mistake_chance=0.15):
    rng = rng or random
    options = [(i, n) for i, p in enumerate(piles) for n in range(1, p + 1)]
    best = best_move(piles, misere)
    if best is None or rng.random() < mistake_chance:
        return rng.choice(options)
    return best


def show(piles):
    for i, p in enumerate(piles, 1):
        console.print(f"  pile {i}: " + "● " * p + f"({p})" if p else f"  pile {i}: [dim]empty[/dim]")


def main(argv):
    misere = "misere" in [a.lower() for a in argv]
    numbers = [a for a in argv if a.isdigit()]
    piles = [int(a) for a in numbers] if numbers else [3, 4, 5]
    if not piles or any(p <= 0 or p > 20 for p in piles) or len(piles) > 8:
        console.print(__doc__)
        return 1
    console.print("[bold]Nim[/bold] - " + ("the last stone loses." if misere else "take the last stone to win."))
    while True:
        show(piles)
        try:
            line = console.input("[bold]your move (pile count, or q)> [/bold]").split()
        except (EOFError, KeyboardInterrupt):
            return 0
        if line and line[0].lower() == "q":
            return 0
        try:
            pile, count = int(line[0]) - 1, int(line[1])
            if not 0 <= pile < len(piles) or not 1 <= count <= piles[pile]:
                raise ValueError
        except (IndexError, ValueError):
            console.print("[red]Type the pile number and how many stones to take, for example: 2 3[/red]")
            continue
        piles[pile] -= count
        if sum(piles) == 0:
            console.print("[bold red]You took the last stone - you lose.[/bold red]" if misere else "[bold green]You took the last stone - you win![/bold green]")
            return 0
        i, n = computer_move(piles, misere)
        piles[i] -= n
        console.print(f"[cyan]The computer takes {n} from pile {i + 1}.[/cyan]")
        if sum(piles) == 0:
            console.print("[bold green]The computer took the last stone - you win![/bold green]" if misere else "[bold red]The computer wins. Try again![/bold red]")
            return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
