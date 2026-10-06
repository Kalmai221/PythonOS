#!/usr/bin/env python3
"""Slide puzzle: put the numbered tiles in order, with the gap in the bottom-right corner.

Type the number of a tile next to the gap to slide it (several in a row are fine: 12 8 7), s to shuffle again, q to quit.
Pick the size with: slide15 3  (8 puzzle), slide15 4 (15 puzzle, the default) or slide15 5.
"""
import random
import sys

from rich.console import Console
from rich.text import Text

console = Console()


def solved_board(n):
    return list(range(1, n * n)) + [0]


def neighbours(index, n):
    x, y = index % n, index // n
    return [i for i, ok in ((index - 1, x > 0), (index + 1, x < n - 1), (index - n, y > 0), (index + n, y < n - 1)) if ok]


def slide(board, n, tile):
    """Slide `tile` into the gap if it touches it. Returns True when it moved."""
    if tile not in board or tile == 0:
        return False
    at, gap = board.index(tile), board.index(0)
    if gap not in neighbours(at, n):
        return False
    board[at], board[gap] = 0, tile
    return True


def shuffled(n, steps=None, rng=None):
    """Shuffle by sliding tiles at random from the finished board, so the puzzle can always be solved."""
    rng = rng or random.Random()
    board = solved_board(n)
    previous = None
    for _ in range(steps or n * n * 20):
        gap = board.index(0)
        options = [i for i in neighbours(gap, n) if i != previous]
        pick = rng.choice(options)
        board[gap], board[pick] = board[pick], 0
        previous = gap
    if board == solved_board(n):
        return shuffled(n, steps, rng)
    return board


def render(board, n):
    out = Text()
    width = len(str(n * n - 1)) + 1
    for y in range(n):
        for x in range(n):
            tile = board[y * n + x]
            out.append(" " * width if tile == 0 else str(tile).rjust(width), style="bold cyan" if tile == y * n + x + 1 else "bold white")
            out.append(" ")
        out.append("\n")
    return out


def execute(args=None):
    n = int(args[0]) if args and args[0] in ("3", "4", "5") else 4
    board = shuffled(n)
    moves = 0
    while True:
        console.print(f"\n[bold]Slide puzzle {n}x{n}[/bold]   moves: {moves}  [dim](correct tiles are cyan)[/dim]")
        console.print(render(board, n))
        if board == solved_board(n):
            console.print(f"[bold green]Solved in {moves} moves![/bold green]")
            return True
        try:
            line = console.input("tile number(s), (s)huffle, (q)uit > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return True
        if line == "q":
            return True
        if line == "s":
            board, moves = shuffled(n), 0
            continue
        for word in line.replace(",", " ").split():
            if word.isdigit() and slide(board, n, int(word)):
                moves += 1
            else:
                console.print(f"[red]{word} cannot slide: it must touch the gap.[/red]")
                break


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
