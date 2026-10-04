#!/usr/bin/env python3
"""2048: slide the tiles with w/a/s/d (+ Enter) and merge matching numbers to reach 2048."""
import random

from rich.console import Console
from rich.table import Table

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
SIZE = 4
COLOURS = {0: "dim", 2: "white", 4: "bright_white", 8: "yellow", 16: "bright_yellow", 32: "orange3", 64: "red",
           128: "bright_cyan", 256: "cyan", 512: "bright_green", 1024: "green", 2048: "bold magenta"}


def slide_row(row):
    """Slide one row to the left. Returns (new row, points scored)."""
    tiles = [n for n in row if n]
    out, gained, i = [], 0, 0
    while i < len(tiles):
        if i + 1 < len(tiles) and tiles[i] == tiles[i + 1]:
            out.append(tiles[i] * 2)
            gained += tiles[i] * 2
            i += 2
        else:
            out.append(tiles[i])
            i += 1
    return out + [0] * (len(row) - len(out)), gained


def move(board, direction):
    """direction in w/a/s/d. Returns (new board, points, changed)."""
    n = len(board)
    rows = [list(r) for r in board]
    if direction in ("w", "s"):
        rows = [list(col) for col in zip(*rows)]
    if direction in ("d", "s"):
        rows = [r[::-1] for r in rows]
    total, new_rows = 0, []
    for r in rows:
        slid, pts = slide_row(r)
        new_rows.append(slid)
        total += pts
    if direction in ("d", "s"):
        new_rows = [r[::-1] for r in new_rows]
    if direction in ("w", "s"):
        new_rows = [list(col) for col in zip(*new_rows)]
    return new_rows, total, new_rows != [list(r) for r in board]


def add_tile(board):
    empty = [(r, c) for r in range(len(board)) for c in range(len(board)) if not board[r][c]]
    if empty:
        r, c = random.choice(empty)
        board[r][c] = 4 if random.random() < 0.1 else 2


def can_move(board):
    return any(move(board, d)[2] for d in "wasd")


def show(board, score, best):
    table = Table(show_header=False, box=None, padding=(0, 1))
    for _ in range(len(board)):
        table.add_column(justify="center", width=6)
    for row in board:
        table.add_row(*[f"[{COLOURS.get(v, 'bold red')}]{v or '.'}[/]" for v in row])
        table.add_row(*[" "] * len(board))
    console.print(f"[bold]2048[/bold]   score [bold]{score}[/bold]   best {max(best, score)}")
    console.print(table)


def main():
    best = (appdata.load("game2048", {}) if appdata else {}).get("best", 0)
    while True:
        board = [[0] * SIZE for _ in range(SIZE)]
        add_tile(board)
        add_tile(board)
        score, won = 0, False
        while True:
            show(board, score, best)
            if not can_move(board):
                console.print("[bold red]No moves left. Game over![/bold red]")
                break
            try:
                key = input("w/a/s/d to slide, q to quit> ").strip().lower()[:1]
            except EOFError:
                return
            if key == "q":
                break
            if key not in ("w", "a", "s", "d"):
                continue
            new, pts, changed = move(board, key)
            if not changed:
                console.print("[yellow]Nothing moved that way.[/yellow]")
                continue
            board, score = new, score + pts
            add_tile(board)
            if not won and any(v >= 2048 for row in board for v in row):
                won = True
                console.print("[bold magenta]You made 2048! Keep going for a higher score.[/bold magenta]")
        if score > best:
            best = score
            if appdata:
                appdata.save("game2048", {"best": best})
            console.print(f"[bold yellow]New best: {best}[/bold yellow]")
        if input("Play again? [y/N] ").strip().lower() != "y":
            return


def execute():
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute()
