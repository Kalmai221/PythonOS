#!/usr/bin/env python3
"""Minesweeper. Commands: o A1 (open), f A1 (flag), q (quit). Opening a square with no mines around it opens its neighbours too.
The first square you open is always safe."""
import random
import sys

from rich.console import Console
from rich.text import Text

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
LEVELS = {"easy": (9, 9, 10), "medium": (12, 12, 24), "hard": (16, 16, 40)}
COLOURS = {1: "blue", 2: "green", 3: "red", 4: "dark_blue", 5: "dark_red", 6: "cyan", 7: "white", 8: "grey50"}


class Board:
    def __init__(self, width, height, mines, rng=None):
        self.w, self.h, self.mines = width, height, mines
        self.rng = rng or random.Random()
        self.mine = [[False] * width for _ in range(height)]
        self.open = [[False] * width for _ in range(height)]
        self.flag = [[False] * width for _ in range(height)]
        self.placed = False
        self.lost = False

    def neighbours(self, x, y):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if (dx or dy) and 0 <= x + dx < self.w and 0 <= y + dy < self.h:
                    yield x + dx, y + dy

    def place(self, safe_x, safe_y):
        """Put the mines down, keeping the first square and its neighbours clear."""
        forbidden = {(safe_x, safe_y), *self.neighbours(safe_x, safe_y)}
        cells = [(x, y) for y in range(self.h) for x in range(self.w) if (x, y) not in forbidden]
        if len(cells) < self.mines:
            cells = [(x, y) for y in range(self.h) for x in range(self.w) if (x, y) != (safe_x, safe_y)]
        for x, y in self.rng.sample(cells, self.mines):
            self.mine[y][x] = True
        self.placed = True

    def count(self, x, y):
        return sum(self.mine[ny][nx] for nx, ny in self.neighbours(x, y))

    def reveal(self, x, y):
        """Open a square. Returns False if it was a mine."""
        if self.flag[y][x] or self.open[y][x]:
            return True
        if not self.placed:
            self.place(x, y)
        if self.mine[y][x]:
            self.lost = True
            self.open[y][x] = True
            return False
        stack = [(x, y)]
        while stack:
            cx, cy = stack.pop()
            if self.open[cy][cx] or self.flag[cy][cx]:
                continue
            self.open[cy][cx] = True
            if self.count(cx, cy) == 0:
                stack.extend(self.neighbours(cx, cy))
        return True

    def toggle_flag(self, x, y):
        if not self.open[y][x]:
            self.flag[y][x] = not self.flag[y][x]

    def won(self):
        return not self.lost and all(self.open[y][x] or self.mine[y][x] for y in range(self.h) for x in range(self.w))

    def flags_left(self):
        return self.mines - sum(f for row in self.flag for f in row)


def parse_square(text, board):
    """'B3' -> (x, y) with letters for columns and numbers for rows; None if it is not a square on the board."""
    text = text.strip().upper()
    if len(text) < 2 or not text[0].isalpha() or not text[1:].isdigit():
        return None
    x, y = ord(text[0]) - 65, int(text[1:]) - 1
    return (x, y) if 0 <= x < board.w and 0 <= y < board.h else None


def render(board, reveal_all=False):
    out = Text("    " + " ".join(chr(65 + x) for x in range(board.w)) + "\n", style="dim")
    for y in range(board.h):
        out.append(f"{y + 1:>2}  ", style="dim")
        for x in range(board.w):
            if board.open[y][x] or (reveal_all and board.mine[y][x]):
                if board.mine[y][x]:
                    out.append("* ", style="bold red")
                else:
                    n = board.count(x, y)
                    out.append((str(n) if n else ".") + " ", style=COLOURS.get(n, "white") if n else "dim")
            elif board.flag[y][x]:
                out.append("F ", style="bold yellow")
            else:
                out.append("# ", style="white")
        out.append("\n")
    return out


def play(level):
    w, h, m = LEVELS[level]
    board = Board(w, h, m)
    console.print(f"[bold]Minesweeper[/bold] ({level}: {w}x{h}, {m} mines)   o A1 = open   f A1 = flag   q = quit")
    while True:
        console.print(render(board), end="")
        console.print(f"[dim]Flags left: {board.flags_left()}[/dim]")
        try:
            line = input("> ").strip().lower().split()
        except EOFError:
            return None
        if not line:
            continue
        if line[0] in ("q", "quit"):
            return None
        if len(line) == 1 and parse_square(line[0], board):
            line = ["o", line[0]]                      # just "B3" opens it
        if len(line) != 2 or line[0] not in ("o", "f"):
            console.print("[yellow]Type  o B3  to open,  f B3  to flag,  q  to quit.[/yellow]")
            continue
        square = parse_square(line[1], board)
        if not square:
            console.print("[yellow]That is not a square on the board.[/yellow]")
            continue
        if line[0] == "f":
            board.toggle_flag(*square)
        elif not board.reveal(*square):
            console.print(render(board, reveal_all=True), end="")
            console.print("[bold red]Boom! You hit a mine.[/bold red]")
            return False
        if board.won():
            console.print(render(board, reveal_all=True), end="")
            console.print("[bold green]You cleared the board![/bold green]")
            return True


def main():
    stats = appdata.load("minesweeper", {}) if appdata else {}
    while True:
        level = input("Level: easy, medium, hard (q to quit)> ").strip().lower() or "easy"
        if level == "q":
            return
        if level not in LEVELS:
            continue
        result = play(level)
        if result is not None and appdata:
            record = stats.setdefault(level, {"won": 0, "lost": 0})
            record["won" if result else "lost"] += 1
            appdata.save("minesweeper", stats)
            console.print(f"[dim]{level}: won {record['won']}, lost {record['lost']}[/dim]")
        if input("Again? [y/N] ").strip().lower() != "y":
            return


def execute(args=None):
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
