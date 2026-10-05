#!/usr/bin/env python3
"""Battleship against the computer. Place your fleet (or let it be placed for you), then take turns firing at squares like B7.
The computer hunts in a checkerboard pattern and, once it hits, follows the ship until it sinks."""
import random
import sys

from rich.console import Console
from rich.text import Text

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
SIZE = 10
FLEET = [("Carrier", 5), ("Battleship", 4), ("Cruiser", 3), ("Submarine", 3), ("Destroyer", 2)]


class Grid:
    def __init__(self):
        self.ship = [[None] * SIZE for _ in range(SIZE)]       # ship name or None
        self.shot = [[False] * SIZE for _ in range(SIZE)]
        self.length = {}

    def can_place(self, x, y, length, horizontal):
        cells = [(x + i, y) if horizontal else (x, y + i) for i in range(length)]
        return all(0 <= cx < SIZE and 0 <= cy < SIZE and self.ship[cy][cx] is None for cx, cy in cells)

    def place(self, name, x, y, length, horizontal):
        if not self.can_place(x, y, length, horizontal):
            return False
        for i in range(length):
            cx, cy = (x + i, y) if horizontal else (x, y + i)
            self.ship[cy][cx] = name
        self.length[name] = length
        return True

    def place_random(self, rng):
        for name, length in FLEET:
            while True:
                if self.place(name, rng.randrange(SIZE), rng.randrange(SIZE), length, rng.random() < 0.5):
                    break

    def fire(self, x, y):
        """Returns ('miss'|'hit'|'sunk'|'again', ship name)."""
        if self.shot[y][x]:
            return "again", None
        self.shot[y][x] = True
        name = self.ship[y][x]
        if name is None:
            return "miss", None
        if all(self.shot[cy][cx] for cy in range(SIZE) for cx in range(SIZE) if self.ship[cy][cx] == name):
            return "sunk", name
        return "hit", name

    def all_sunk(self):
        return all(self.shot[y][x] for y in range(SIZE) for x in range(SIZE) if self.ship[y][x])


class Hunter:
    """The computer's shooting strategy: search in a checkerboard pattern; after a hit, keep firing around the hits that are not
    yet part of a sunk ship, preferring to extend a line of two or more hits."""

    def __init__(self, rng):
        self.rng = rng
        self.hits = []                    # hit squares whose ship is still afloat

    def next_shot(self, grid):
        def free(x, y):
            return 0 <= x < SIZE and 0 <= y < SIZE and not grid.shot[y][x]
        line, around = [], []
        for x, y in self.hits:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if free(x + dx, y + dy):
                    # a neighbour that continues a pair of hits in the same direction is a better bet
                    if (x - dx, y - dy) in self.hits:
                        line.append((x + dx, y + dy))
                    else:
                        around.append((x + dx, y + dy))
        if line:
            return self.rng.choice(line)
        if around:
            return self.rng.choice(around)
        cells = [(x, y) for y in range(SIZE) for x in range(SIZE) if free(x, y) and (x + y) % 2 == 0]
        cells = cells or [(x, y) for y in range(SIZE) for x in range(SIZE) if free(x, y)]
        return self.rng.choice(cells)

    def result(self, x, y, outcome, grid=None):
        if outcome in ("hit", "sunk"):
            self.hits.append((x, y))
        if outcome == "sunk" and grid is not None:
            name = grid.ship[y][x]
            self.hits = [(hx, hy) for hx, hy in self.hits if grid.ship[hy][hx] != name]


def parse_square(text):
    text = text.strip().upper()
    if len(text) >= 2 and text[0].isalpha() and text[1:].isdigit():
        x, y = ord(text[0]) - 65, int(text[1:]) - 1
        if 0 <= x < SIZE and 0 <= y < SIZE:
            return x, y
    return None


def render(own, enemy):
    out = Text("   YOUR FLEET" + " " * 12 + "ENEMY WATERS\n   " + " ".join(chr(65 + x) for x in range(SIZE)) + "     "
               + " ".join(chr(65 + x) for x in range(SIZE)) + "\n", style="dim")
    for y in range(SIZE):
        out.append(f"{y + 1:>2} ", style="dim")
        for x in range(SIZE):
            ship, shot = own.ship[y][x], own.shot[y][x]
            out.append(("X " if shot and ship else "o " if shot else "S " if ship else "~ "),
                       style="bold red" if shot and ship else "white" if shot else "green" if ship else "blue")
        out.append("   ")
        for x in range(SIZE):
            ship, shot = enemy.ship[y][x], enemy.shot[y][x]
            out.append(("X " if shot and ship else "o " if shot else "~ "), style="bold red" if shot and ship else "white" if shot else "blue")
        out.append("\n")
    return out


def place_fleet(grid, rng):
    answer = input("Place your ships yourself? [y/N] ").strip().lower()
    if answer != "y":
        grid.place_random(rng)
        return
    for name, length in FLEET:
        while True:
            console.print(render(grid, Grid()), end="")
            text = input(f"{name} ({length}) - start square and h or v, like B3 h> ").strip().lower().split()
            if len(text) == 2 and parse_square(text[0]) and text[1] in ("h", "v"):
                x, y = parse_square(text[0])
                if grid.place(name, x, y, length, text[1] == "h"):
                    break
            console.print("[yellow]It does not fit there. Example: B3 h (horizontal) or B3 v (down).[/yellow]")


def play(rng=None):
    rng = rng or random.Random()
    mine, theirs = Grid(), Grid()
    theirs.place_random(rng)
    place_fleet(mine, rng)
    hunter = Hunter(rng)
    console.print("[bold]Battleship[/bold]: fire at a square like B7. X = hit, o = miss. q to quit.")
    while True:
        console.print(render(mine, theirs), end="")
        try:
            text = input("Fire> ").strip()
        except EOFError:
            return None
        if text.lower() in ("q", "quit"):
            return None
        square = parse_square(text)
        if not square:
            console.print("[yellow]Type a square like B7.[/yellow]")
            continue
        outcome, name = theirs.fire(*square)
        if outcome == "again":
            console.print("[yellow]You already fired there.[/yellow]")
            continue
        console.print({"miss": "[blue]Miss.[/blue]", "hit": "[bold red]Hit![/bold red]", "sunk": f"[bold red]You sank their {name}![/bold red]"}[outcome])
        if theirs.all_sunk():
            console.print(render(mine, theirs), end="")
            console.print("[bold green]You sank the whole enemy fleet - victory![/bold green]")
            return True
        cx, cy = hunter.next_shot(mine)
        result, ship = mine.fire(cx, cy)
        hunter.result(cx, cy, result, mine)
        console.print(f"[dim]The computer fires at {chr(65 + cx)}{cy + 1}: {result}" + (f" - your {ship} is sunk!" if result == "sunk" else "") + "[/dim]")
        if mine.all_sunk():
            console.print(render(mine, theirs), end="")
            console.print("[bold red]Your fleet is sunk. Defeat.[/bold red]")
            return False


def main():
    stats = appdata.load("battleship", {"won": 0, "lost": 0}) if appdata else None
    while True:
        result = play()
        if result is None:
            return
        if stats is not None:
            stats["won" if result else "lost"] += 1
            appdata.save("battleship", stats)
            console.print(f"[dim]Won {stats['won']}, lost {stats['lost']}[/dim]")
        if input("Again? [y/N] ").strip().lower() != "y":
            return


def execute(args=None):
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
