#!/usr/bin/env python3
"""Dice roller.

    roll d20                  one twenty-sided die
    roll 2d6+3                two six-sided dice and add 3
    roll 4d6kh3               roll four, keep the highest three (kl = lowest)
    roll d20 d20+5 3d8        several rolls in one go
    roll adv  /  roll dis     a d20 with advantage (the better of two) or disadvantage
"""
import random
import re
import sys

from rich.console import Console

console = Console()
PATTERN = re.compile(r"^(\d*)d(\d+)(?:(kh|kl)(\d+))?([+-]\d+)?$", re.I)
rng = random.SystemRandom()


def parse(text):
    """(count, sides, keep mode or None, keep count, modifier) for an expression like 4d6kh3+2, or None when it is not dice."""
    match = PATTERN.match(text.replace(" ", ""))
    if not match:
        return None
    count = int(match.group(1) or 1)
    sides = int(match.group(2))
    keep = int(match.group(4)) if match.group(4) else 0
    if not 1 <= count <= 100 or not 2 <= sides <= 1000 or (match.group(3) and not 1 <= keep <= count):
        return None
    return count, sides, (match.group(3) or "").lower() or None, keep, int(match.group(5) or 0)


def roll(expression, generator=None):
    """(total, [every die rolled], [the dice kept], modifier) for a parsed expression."""
    count, sides, mode, keep, modifier = expression
    generator = generator or rng
    dice = [generator.randint(1, sides) for _ in range(count)]
    kept = dice
    if mode:
        ordered = sorted(dice, reverse=(mode == "kh"))
        kept = ordered[:keep]
    return sum(kept) + modifier, dice, kept, modifier


def describe(text, result):
    total, dice, kept, modifier = result
    shown = " + ".join(str(d) for d in dice)
    if len(kept) != len(dice):
        dropped = list(dice)
        for k in kept:
            dropped.remove(k)
        shown = " + ".join(str(d) for d in kept) + "   (dropped " + ", ".join(str(d) for d in dropped) + ")"
    extra = f" {'+' if modifier > 0 else '-'} {abs(modifier)}" if modifier else ""
    return f"{text}: [{shown}]{extra} = {total}"


def execute(args=None):
    args = [a for a in (args or []) if a]
    if not args:
        args = ["d20"]
    ok = True
    for text in args:
        if text.lower() in ("adv", "advantage", "dis", "disadvantage"):
            a, b = rng.randint(1, 20), rng.randint(1, 20)
            best = max(a, b) if text.lower().startswith("adv") else min(a, b)
            console.print(f"d20 with {'advantage' if text.lower().startswith('adv') else 'disadvantage'}: {a}, {b} -> [bold]{best}[/bold]")
            continue
        expression = parse(text)
        if expression is None:
            console.print(f"[yellow]'{text}' is not dice. Try d20, 2d6+3 or 4d6kh3 (up to 100 dice, 1000 sides).[/yellow]", highlight=False)
            ok = False
            continue
        result = roll(expression)
        line = describe(text, result)
        head, _, tail = line.rpartition("= ")
        console.print(f"{head}= [bold]{tail}[/bold]", markup=True, highlight=False) if "[" not in head.replace(": [", "").replace("]", "") else console.print(line, markup=False, highlight=False)
    return ok


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
