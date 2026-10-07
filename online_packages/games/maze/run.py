#!/usr/bin/env python3
"""Maze: find your way from the top-left (you, @) to the bottom-right (the star).

    maze            a medium maze
    maze small      small, medium or large

Type moves and press Enter: w a s d (up, left, down, right), several at once like ddwdd. h shows the way, n a new maze, q quits.
"""
import collections
import random
import sys

from rich.console import Console

console = Console()
SIZES = {"small": (8, 6), "medium": (14, 9), "large": (22, 12)}
DIRS = {"w": (0, -1), "a": (-1, 0), "s": (0, 1), "d": (1, 0)}


def generate(width, height, rng=None):
    """A perfect maze (exactly one route between any two cells). Returns {(x, y): set of cells you can walk to}."""
    rng = rng or random.Random()
    open_to = {(x, y): set() for x in range(width) for y in range(height)}
    seen, stack = {(0, 0)}, [(0, 0)]
    while stack:
        x, y = stack[-1]
        options = [(x + dx, y + dy) for dx, dy in DIRS.values() if (x + dx, y + dy) in open_to and (x + dx, y + dy) not in seen]
        if not options:
            stack.pop()
            continue
        nxt = rng.choice(options)
        open_to[(x, y)].add(nxt)
        open_to[nxt].add((x, y))
        seen.add(nxt)
        stack.append(nxt)
    return open_to


def solve(maze, start, goal):
    """The shortest list of cells from start to goal (both included), or [] when there is no way."""
    came = {start: None}
    queue = collections.deque([start])
    while queue:
        here = queue.popleft()
        if here == goal:
            path = []
            while here is not None:
                path.append(here)
                here = came[here]
            return path[::-1]
        for n in maze[here]:
            if n not in came:
                came[n] = here
                queue.append(n)
    return []


def move(maze, position, letters):
    """Apply w/a/s/d moves; a move into a wall is ignored. Returns the new position."""
    for ch in letters.lower():
        if ch in DIRS:
            target = (position[0] + DIRS[ch][0], position[1] + DIRS[ch][1])
            if target in maze[position]:
                position = target
    return position


def draw(maze, width, height, player, goal, path=()):
    rows = ["+" + "---+" * width]
    on_path = set(path)
    for y in range(height):
        line, below = "|", "+"
        for x in range(width):
            cell = (x, y)
            mark = " @ " if cell == player else " * " if cell == goal else " . " if cell in on_path else "   "
            line += mark + (" " if (x + 1, y) in maze[cell] else "|")
            below += ("   " if (x, y + 1) in maze[cell] else "---") + "+"
        rows += [line, below]
    return "\n".join(rows)


def main(argv):
    size = SIZES.get(argv[0].lower() if argv else "medium")
    if size is None:
        console.print(__doc__)
        return 1
    width, height = size
    maze, player, goal, moves, hint = generate(width, height), (0, 0), (width - 1, height - 1), 0, ()
    while True:
        console.print(draw(maze, width, height, player, goal, hint))
        if player == goal:
            console.print(f"[bold green]You found the way out in {moves} moves![/bold green] Type n for another maze or q to quit.")
        try:
            line = console.input("[bold]move> [/bold]").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return 0
        if line in ("q", "quit"):
            return 0
        if line == "n":
            maze, player, moves, hint = generate(width, height), (0, 0), 0, ()
        elif line == "h":
            hint = solve(maze, player, goal)
        elif line:
            before = player
            player = move(maze, player, line)
            moves += sum(1 for c in line if c in DIRS)
            hint = () if player != before else hint


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
