#!/usr/bin/env python3
"""Sudoku: a generator (easy, medium, hard), a hint, a checker and a solver. Fill every row, column and 3x3 box with 1-9.
Commands: B3 7 (put 7 in column B, row 3), clear B3, hint, check, solve, new, q."""
import copy
import random
import sys

from rich.console import Console
from rich.text import Text

console = Console()
CLUES = {"easy": 40, "medium": 32, "hard": 26}


def candidates(grid, r, c):
    if grid[r][c]:
        return set()
    used = set(grid[r]) | {grid[i][c] for i in range(9)}
    br, bc = r // 3 * 3, c // 3 * 3
    used |= {grid[i][j] for i in range(br, br + 3) for j in range(bc, bc + 3)}
    return set(range(1, 10)) - used


def solve(grid, rng=None, limit=None):
    """Fill the grid by backtracking (fewest candidates first). Returns True when solved; the grid is changed in place."""
    best, options = None, None
    for r in range(9):
        for c in range(9):
            if grid[r][c] == 0:
                cand = candidates(grid, r, c)
                if not cand:
                    return False
                if options is None or len(cand) < len(options):
                    best, options = (r, c), cand
                    if len(cand) == 1:
                        break
        if options is not None and len(options) == 1:
            break
    if best is None:
        return True
    values = list(options)
    if rng:
        rng.shuffle(values)
    r, c = best
    for v in values:
        grid[r][c] = v
        if solve(grid, rng):
            return True
    grid[r][c] = 0
    return False


def count_solutions(grid, cap=2):
    """How many solutions the puzzle has, counting up to cap (a proper puzzle has exactly one)."""
    best, options = None, None
    for r in range(9):
        for c in range(9):
            if grid[r][c] == 0:
                cand = candidates(grid, r, c)
                if not cand:
                    return 0
                if options is None or len(cand) < len(options):
                    best, options = (r, c), cand
    if best is None:
        return 1
    total = 0
    r, c = best
    for v in options:
        grid[r][c] = v
        total += count_solutions(grid, cap - total)
        if total >= cap:
            break
    grid[r][c] = 0
    return total


def generate(level="medium", seed=None):
    """(puzzle, solution). Cells are removed one by one, keeping the solution unique."""
    rng = random.Random(seed)
    solution = [[0] * 9 for _ in range(9)]
    solve(solution, rng)
    puzzle = copy.deepcopy(solution)
    cells = [(r, c) for r in range(9) for c in range(9)]
    rng.shuffle(cells)
    clues = 81
    for r, c in cells:
        if clues <= CLUES[level]:
            break
        keep = puzzle[r][c]
        puzzle[r][c] = 0
        if count_solutions(copy.deepcopy(puzzle)) != 1:
            puzzle[r][c] = keep
        else:
            clues -= 1
    return puzzle, solution


def conflicts(grid):
    """Set of (row, col) that break a rule (a repeated number in a row, column or box)."""
    bad = set()
    for i in range(9):
        for unit in ([(i, j) for j in range(9)], [(j, i) for j in range(9)],
                     [(i // 3 * 3 + a, i % 3 * 3 + b) for a in range(3) for b in range(3)]):
            seen = {}
            for r, c in unit:
                v = grid[r][c]
                if v:
                    if v in seen:
                        bad.add((r, c))
                        bad.add(seen[v])
                    seen[v] = (r, c)
    return bad


def render(grid, given, bad=()):
    out = Text("    A B C   D E F   G H I\n", style="dim")
    for r in range(9):
        if r and r % 3 == 0:
            out.append("   -------+-------+-------\n", style="dim")
        out.append(f"{r + 1:>2} ", style="dim")
        for c in range(9):
            if c and c % 3 == 0:
                out.append("| ", style="dim")
            v = grid[r][c]
            style = "bold red" if (r, c) in bad else "bold white" if given[r][c] else "cyan"
            out.append((str(v) if v else ".") + " ", style=style if v else "dim")
        out.append("\n")
    return out


def parse_cell(text):
    text = text.strip().upper()
    if len(text) == 2 and text[0] in "ABCDEFGHI" and text[1] in "123456789":
        return int(text[1]) - 1, ord(text[0]) - 65
    return None


def play(level):
    puzzle, solution = generate(level)
    grid = copy.deepcopy(puzzle)
    given = [[bool(v) for v in row] for row in puzzle]
    console.print(f"[bold]Sudoku[/bold] ({level})  B3 7 = put 7 in B3   clear B3   hint   check   solve   new   q")
    while True:
        console.print(render(grid, given, conflicts(grid)), end="")
        if all(all(row) for row in grid) and not conflicts(grid):
            console.print("[bold green]Solved! Well done.[/bold green]")
            return True
        try:
            parts = input("> ").strip().lower().split()
        except EOFError:
            return None
        if not parts:
            continue
        cmd = parts[0]
        if cmd in ("q", "quit"):
            return None
        if cmd == "new":
            return "new"
        if cmd == "solve":
            console.print(render(solution, given), end="")
            return False
        if cmd == "check":
            wrong = [(r, c) for r in range(9) for c in range(9) if grid[r][c] and grid[r][c] != solution[r][c]]
            console.print("[green]Everything you have entered is correct so far.[/green]" if not wrong
                          else f"[yellow]{len(wrong)} entry(ies) are wrong: " + ", ".join(f"{chr(65 + c)}{r + 1}" for r, c in wrong) + "[/yellow]")
            continue
        if cmd == "hint":
            empty = [(r, c) for r in range(9) for c in range(9) if not grid[r][c]]
            if empty:
                r, c = min(empty, key=lambda rc: len(candidates(grid, *rc)) or 10)
                grid[r][c] = solution[r][c]
                console.print(f"[dim]Hint: {chr(65 + c)}{r + 1} is {solution[r][c]}.[/dim]")
            continue
        cell = parse_cell(parts[0] if cmd != "clear" else (parts[1] if len(parts) > 1 else ""))
        if not cell:
            console.print("[yellow]Try  B3 7  or  clear B3.[/yellow]")
            continue
        r, c = cell
        if given[r][c]:
            console.print("[yellow]That square is part of the puzzle.[/yellow]")
        elif cmd == "clear":
            grid[r][c] = 0
        elif len(parts) > 1 and parts[1] in tuple("123456789"):
            grid[r][c] = int(parts[1])
        else:
            console.print("[yellow]Put a number from 1 to 9, for example  B3 7.[/yellow]")


def main():
    while True:
        level = input("Level: easy, medium, hard (q to quit)> ").strip().lower() or "medium"
        if level == "q":
            return
        if level not in CLUES:
            continue
        with console.status("Making a puzzle..."):
            pass
        while True:
            result = play(level)
            if result == "new":
                continue
            break
        if result is None:
            return
        if input("Another? [y/N] ").strip().lower() != "y":
            return


def execute(args=None):
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
