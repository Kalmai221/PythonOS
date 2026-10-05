#!/usr/bin/env python3
"""Flood: start in the top-left corner and turn it into the colour you choose; every touching square of that colour joins in.
Make the whole board one colour within the move limit. Type a colour letter each turn: R G B Y P C."""
import random
import sys

from rich.console import Console
from rich.text import Text

console = Console()
COLOURS = "RGBYPC"
STYLE = {"R": "red", "G": "green", "B": "blue", "Y": "yellow", "P": "magenta", "C": "cyan"}
SIZES = {"small": (8, 14), "medium": (12, 22), "large": (16, 30)}   # (side, moves)


def make_board(size, rng=None):
    rng = rng or random.Random()
    return [[rng.choice(COLOURS) for _ in range(size)] for _ in range(size)]


def region(board):
    """The set of squares joined to the top-left corner (same colour, touching)."""
    n = len(board)
    colour = board[0][0]
    seen, stack = set(), [(0, 0)]
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or not (0 <= x < n and 0 <= y < n) or board[y][x] != colour:
            continue
        seen.add((x, y))
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return seen


def flood(board, colour):
    """Turn the corner region into `colour`. Returns how many squares joined it."""
    if board[0][0] == colour:
        return 0
    before = region(board)
    for x, y in before:
        board[y][x] = colour
    return len(region(board)) - len(before)


def solved(board):
    return len(region(board)) == len(board) ** 2


def render(board):
    out = Text()
    for row in board:
        for ch in row:
            out.append("  ", style=f"on {STYLE[ch]}")
        out.append("\n")
    return out


def play(size_name):
    size, limit = SIZES[size_name]
    board = make_board(size)
    moves = 0
    console.print(f"[bold]Flood[/bold] ({size_name}): one colour in {limit} moves. Type R G B Y P or C.")
    while True:
        console.print(render(board), end="")
        console.print(f"Moves {moves}/{limit}   Joined {len(region(board))}/{size * size}")
        if solved(board):
            console.print(f"[bold green]Flooded in {moves} moves![/bold green]")
            return moves
        if moves >= limit:
            console.print("[bold red]Out of moves.[/bold red]")
            return False
        try:
            pick = input("colour> ").strip().upper()
        except EOFError:
            return None
        if pick in ("Q", "QUIT"):
            return None
        if len(pick) != 1 or pick not in COLOURS:
            console.print(f"[yellow]Pick one of {COLOURS}.[/yellow]")
            continue
        if flood(board, pick) == 0:
            console.print("[yellow]That changes nothing - pick a different colour.[/yellow]")
            continue
        moves += 1


def main():
    while True:
        name = input("Size: small, medium, large (q to quit)> ").strip().lower() or "small"
        if name == "q":
            return
        if name not in SIZES:
            continue
        if play(name) is None:
            return
        if input("Again? [y/N] ").strip().lower() != "y":
            return


def execute(args=None):
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
