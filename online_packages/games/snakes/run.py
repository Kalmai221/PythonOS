#!/usr/bin/env python3
"""Snakes and ladders against the computer. Press Enter to roll. Ladders take you up, snakes take you down, and you must land on 100 exactly.

    snakes                  you against the computer
    snakes 3                you and two computer players (2 to 4 players)
"""
import random
import sys

from rich.console import Console

console = Console()
LADDERS = {1: 38, 4: 14, 9: 31, 21: 42, 28: 84, 36: 44, 51: 67, 71: 91, 80: 100}
SNAKES = {16: 6, 47: 26, 49: 11, 56: 53, 62: 19, 64: 60, 87: 24, 93: 73, 95: 75, 98: 78}
GOAL = 100
NAMES = ["You", "Computer", "Robot", "Machine"]


def move(position, roll):
    """(new position, 'ladder'/'snake'/None). A roll that would pass 100 does not move; 100 is reached exactly."""
    target = position + roll
    if target > GOAL:
        return position, None
    if target in LADDERS:
        return LADDERS[target], "ladder"
    if target in SNAKES:
        return SNAKES[target], "snake"
    return target, None


def turn(position, rng=random):
    """One player's turn: a roll of the die and where it leads. -> (roll, new position, 'ladder'/'snake'/None)."""
    roll = rng.randint(1, 6)
    new, event = move(position, roll)
    return roll, new, event


def board(positions):
    """Ten lines of ten squares, 100 at the top left, the way the board is printed, with the players marked."""
    at = {}
    for number, position in enumerate(positions):
        at.setdefault(position, []).append(NAMES[number][0])
    lines = []
    for row in range(9, -1, -1):
        squares = list(range(row * 10 + 1, row * 10 + 11))
        if row % 2 == 1:
            squares.reverse()
        cells = []
        for square in squares:
            marker = "".join(at.get(square, []))
            label = f"{square:3}"
            if square in LADDERS:
                label = f"[green]{square:3}[/green]"
            elif square in SNAKES:
                label = f"[red]{square:3}[/red]"
            cells.append(f"{label}[bold yellow]{marker:<2}[/bold yellow]" if marker else f"{label}  ")
        lines.append(" ".join(cells))
    return "\n".join(lines)


def main(argv):
    players = 2
    for word in argv:
        if word.isdigit() and 2 <= int(word) <= 4:
            players = int(word)
    positions = [0] * players
    console.print("[bold]Snakes and ladders[/bold]  [green]green: ladder foot[/green]  [red]red: snake head[/red]")
    current = 0
    while True:
        if current == 0:
            try:
                console.input("\n[bold]Press Enter to roll[/bold] (Ctrl+C quits) ")
            except (EOFError, KeyboardInterrupt):
                console.print()
                return 0
        roll, positions[current], event = turn(positions[current])
        line = f"{NAMES[current]} rolled {roll} and is on {positions[current]}"
        if event == "ladder":
            line += " - [green]a ladder, up![/green]"
        elif event == "snake":
            line += " - [red]a snake, down![/red]"
        console.print(line)
        if positions[current] == GOAL:
            console.print(board(positions))
            console.print(f"\n[bold {'green' if current == 0 else 'red'}]{NAMES[current]} reached 100 and won![/bold {'green' if current == 0 else 'red'}]")
            return 0
        if current == 0 or current == players - 1:
            console.print(board(positions))
        current = (current + 1) % players


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
