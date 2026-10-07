#!/usr/bin/env python3
"""Life: Conway's Game of Life. Cells live, die and are born by simple rules, and patterns walk, pulse and grow.

    life                   a random start
    life glider            a pattern: glider, blinker, toad, beacon, pulsar, rpentomino, gun (a glider gun)
    life glider 200        how many generations to run (Ctrl+C stops earlier)

A cell with 2 or 3 neighbours survives; an empty cell with exactly 3 neighbours comes alive; everything else dies.
"""
import random
import sys
import time

from rich.console import Console

console = Console()
PATTERNS = {
    "glider": [".#.", "..#", "###"],
    "blinker": ["###"],
    "toad": [".###", "###."],
    "beacon": ["##..", "##..", "..##", "..##"],
    "pulsar": ["..###...###..", ".............", "#....#.#....#", "#....#.#....#", "#....#.#....#", "..###...###..", ".............",
               "..###...###..", "#....#.#....#", "#....#.#....#", "#....#.#....#", ".............", "..###...###.."],
    "rpentomino": [".##", "##.", ".#."],
    "gun": ["........................#...........", "......................#.#...........", "............##......##............##",
            "...........#...#....##............##", "##........#.....#...##..................", "##........#...#.##....#.#...........",
            "..........#.....#.......#...........", "...........#...#....................", "............##......................"],
}


def parse(rows, offset=(0, 0)):
    return {(x + offset[0], y + offset[1]) for y, row in enumerate(rows) for x, c in enumerate(row) if c == "#"}


def step(cells):
    """The next generation of a set of live (x, y) cells on an unbounded board."""
    counts = {}
    for x, y in cells:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    key = (x + dx, y + dy)
                    counts[key] = counts.get(key, 0) + 1
    return {c for c, n in counts.items() if n == 3 or (n == 2 and c in cells)}


def render(cells, width, height, origin=(0, 0)):
    """Text rows of the board: ● for a live cell."""
    ox, oy = origin
    return ["".join("●" if (x + ox, y + oy) in cells else "·" for x in range(width)) for y in range(height)]


def random_start(width, height, rng=None):
    rng = rng or random.Random()
    return {(x, y) for x in range(width) for y in range(height) if rng.random() < 0.28}


def main(argv):
    width = min(max(console.size.width - 2, 20), 78)
    height = min(max(console.size.height - 4, 8), 28)
    name = argv[0].lower() if argv else "random"
    try:
        generations = int(argv[1]) if len(argv) > 1 else 300
    except ValueError:
        console.print(__doc__)
        return 1
    if name == "random":
        cells = random_start(width, height)
    elif name in PATTERNS:
        rows = PATTERNS[name]
        cells = parse(rows, ((width - len(rows[0])) // 2, (height - len(rows)) // 2))
    else:
        console.print(__doc__)
        return 1
    try:
        for generation in range(generations + 1):
            console.clear()
            console.print(f"[bold]Life[/bold] - generation {generation}, {len(cells)} alive   (Ctrl+C to stop)")
            console.print("\n".join(render(cells, width, height)))
            if not cells:
                console.print("Everything died out.")
                break
            time.sleep(0.12)
            cells = step(cells)
    except KeyboardInterrupt:
        console.print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
