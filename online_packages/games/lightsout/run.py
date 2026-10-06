#!/usr/bin/env python3
"""Lights Out: pressing a light flips it and its four neighbours. Turn every light off.

Type a cell like b3 (column letter, row number) to press it, h for a hint, n for a new puzzle, q to quit.
"""
import random
import sys

from rich.console import Console
from rich.text import Text

console = Console()
SIZE = 5


def press(board, x, y):
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < SIZE and 0 <= ny < SIZE:
            board[ny][nx] ^= 1


def new_board(presses=8, rng=None):
    """A puzzle that can always be solved: start dark and press random cells."""
    rng = rng or random.Random()
    board = [[0] * SIZE for _ in range(SIZE)]
    while not any(any(row) for row in board):
        board = [[0] * SIZE for _ in range(SIZE)]
        for _ in range(presses):
            press(board, rng.randrange(SIZE), rng.randrange(SIZE))
    return board


def solved(board):
    return not any(any(row) for row in board)


def solve(board):
    """Cells to press (a list of (x, y)) that turn every light off: chase the lights down the rows, then fix the top row by trying each of
    its 2**5 presses. Always finds an answer for 5x5 boards that can be solved."""
    best = None
    for mask in range(1 << SIZE):
        work = [row[:] for row in board]
        pressed = []
        for x in range(SIZE):
            if mask >> x & 1:
                press(work, x, 0)
                pressed.append((x, 0))
        for y in range(1, SIZE):
            for x in range(SIZE):
                if work[y - 1][x]:
                    press(work, x, y)
                    pressed.append((x, y))
        if solved(work) and (best is None or len(pressed) < len(best)):
            best = pressed
    return best


def parse_cell(text):
    text = text.strip().lower()
    if len(text) == 2 and text[0] in "abcde" and text[1] in "12345":
        return "abcde".index(text[0]), int(text[1]) - 1
    return None


def render(board):
    out = Text("    a  b  c  d  e\n", style="dim")
    for y, row in enumerate(board):
        out.append(f"  {y + 1} ", style="dim")
        for cell in row:
            out.append("██ " if cell else "·· ", style="bold yellow" if cell else "grey37")
        out.append("\n")
    return out


def execute(args=None):
    board = new_board()
    moves = 0
    while True:
        console.print(f"\n[bold]Lights Out[/bold]   presses: {moves}")
        console.print(render(board))
        if solved(board):
            console.print(f"[bold green]All lights are off in {moves} presses![/bold green]")
            if console.input("Play again? (y/n) ").strip().lower() != "y":
                return True
            board, moves = new_board(), 0
            continue
        try:
            line = console.input("cell (like b3), (h)int, (n)ew, (q)uit > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return True
        if line == "q":
            return True
        if line == "n":
            board, moves = new_board(), 0
        elif line == "h":
            answer = solve(board)
            x, y = answer[0] if answer else (0, 0)
            console.print(f"[cyan]Try {'abcde'[x]}{y + 1}[/cyan]")
        elif parse_cell(line):
            press(board, *parse_cell(line))
            moves += 1
        else:
            console.print("[red]Type a cell like b3.[/red]")


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
