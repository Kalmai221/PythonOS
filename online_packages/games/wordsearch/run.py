#!/usr/bin/env python3
"""Word search: find the hidden words in the grid. They run left-right, top-bottom or diagonally (and backwards on harder levels).
To claim a word type its start and end squares, like  B2 B7  (column letter then row number), or just the word itself, like  planet.
Commands: list, show, hint, reveal, new, q."""
import random
import sys

from rich.console import Console
from rich.text import Text

console = Console()

THEMES = {
    "space": ["planet", "comet", "orbit", "galaxy", "rocket", "moon", "star", "meteor", "nebula", "saturn", "venus", "mars"],
    "animals": ["tiger", "zebra", "otter", "eagle", "panda", "koala", "whale", "camel", "horse", "rabbit", "falcon", "lizard"],
    "computers": ["kernel", "shell", "python", "memory", "binary", "pixel", "cursor", "script", "router", "server", "folder", "cloud"],
    "food": ["bread", "pizza", "pasta", "apple", "lemon", "olive", "honey", "butter", "cheese", "banana", "carrot", "garlic"],
    "nature": ["river", "ocean", "forest", "desert", "island", "valley", "mountain", "meadow", "glacier", "canyon", "lagoon", "tundra"],
}
LEVELS = {"easy": (10, 6, False), "medium": (12, 8, True), "hard": (15, 10, True)}      # size, word count, allow backwards/diagonal-up
DIRS = [(0, 1), (1, 0), (1, 1)]
DIRS_HARD = DIRS + [(0, -1), (-1, 0), (-1, -1), (1, -1), (-1, 1)]


class Puzzle:
    def __init__(self, theme="space", level="easy", rng=None):
        self.rng = rng or random.Random()
        size, count, hard = LEVELS[level]
        self.size = size
        self.grid = [[None] * size for _ in range(size)]
        self.words, self.found = {}, set()               # word -> (start, direction)
        pool = [w for w in THEMES[theme] if len(w) <= size]
        self.rng.shuffle(pool)
        pool.sort(key=len, reverse=True)
        for word in pool:
            if len(self.words) >= count:
                break
            self.try_place(word, DIRS_HARD if hard else DIRS)
        letters = "abcdefghijklmnopqrstuvwxyz"
        for r in range(size):
            for c in range(size):
                if self.grid[r][c] is None:
                    self.grid[r][c] = self.rng.choice(letters)

    def try_place(self, word, dirs):
        for _ in range(200):
            dr, dc = self.rng.choice(dirs)
            r, c = self.rng.randrange(self.size), self.rng.randrange(self.size)
            cells = [(r + dr * i, c + dc * i) for i in range(len(word))]
            if all(0 <= y < self.size and 0 <= x < self.size and self.grid[y][x] in (None, word[i]) for i, (y, x) in enumerate(cells)):
                for (y, x), ch in zip(cells, word):
                    self.grid[y][x] = ch
                self.words[word] = ((r, c), (dr, dc))
                return True
        return False

    def cells_of(self, word):
        (r, c), (dr, dc) = self.words[word]
        return [(r + dr * i, c + dc * i) for i in range(len(word))]

    def claim_squares(self, a, b):
        """Try to claim the word that runs from square a to square b. Returns the word or None."""
        for word in self.words:
            cells = self.cells_of(word)
            if (cells[0], cells[-1]) in ((a, b), (b, a)):
                self.found.add(word)
                return word
        return None

    def claim_word(self, text):
        text = text.strip().lower()
        if text in self.words:
            self.found.add(text)
            return True
        return False

    def done(self):
        return len(self.found) == len(self.words)

    def render(self, reveal=False):
        marked = set()
        for w in (self.words if reveal else self.found):
            marked.update(self.cells_of(w))
        out = Text("    " + " ".join(chr(65 + c) for c in range(self.size)) + "\n", style="dim")
        for r in range(self.size):
            out.append(f"{r + 1:>2}  ", style="dim")
            for c in range(self.size):
                out.append(self.grid[r][c].upper() + " ", style="bold green" if (r, c) in marked else "white")
            out.append("\n")
        return out


def parse_square(text, size):
    text = text.strip().upper()
    if len(text) >= 2 and text[0].isalpha() and text[1:].isdigit():
        c, r = ord(text[0]) - 65, int(text[1:]) - 1
        if 0 <= r < size and 0 <= c < size:
            return r, c
    return None


def play(theme, level):
    puzzle = Puzzle(theme, level)
    console.print(f"[bold]Word search[/bold] ({theme}, {level}): find {len(puzzle.words)} words. Type a word, or its start and end squares like B2 B7.")
    while not puzzle.done():
        console.print(puzzle.render(), end="")
        remaining = sorted(w for w in puzzle.words if w not in puzzle.found)
        console.print("Words: " + "  ".join(f"[dim strike]{w}[/dim strike]" if w in puzzle.found else w for w in sorted(puzzle.words)))
        try:
            parts = input("> ").strip().lower().split()
        except EOFError:
            return None
        if not parts:
            continue
        if parts[0] in ("q", "quit"):
            return None
        if parts[0] == "new":
            return "new"
        if parts[0] == "reveal":
            console.print(puzzle.render(reveal=True), end="")
            return False
        if parts[0] == "hint":
            word = puzzle.rng.choice(remaining)
            (r, c), _ = puzzle.words[word]
            console.print(f"[dim]Hint: '{word}' starts at {chr(65 + c)}{r + 1}.[/dim]")
            continue
        if len(parts) == 1 and puzzle.claim_word(parts[0]):
            console.print(f"[green]Found {parts[0]}![/green]")
        elif len(parts) == 2 and all(parse_square(p, puzzle.size) for p in parts):
            word = puzzle.claim_squares(parse_square(parts[0], puzzle.size), parse_square(parts[1], puzzle.size))
            console.print(f"[green]Found {word}![/green]" if word else "[yellow]No word runs between those squares.[/yellow]")
        else:
            console.print("[yellow]Type a word, or start and end squares like B2 B7.[/yellow]")
    console.print(puzzle.render(), end="")
    console.print("[bold green]You found every word![/bold green]")
    return True


def main():
    while True:
        theme = input(f"Theme: {', '.join(THEMES)} (q to quit)> ").strip().lower() or "space"
        if theme == "q":
            return
        level = input("Level: easy, medium, hard> ").strip().lower() or "easy"
        if theme not in THEMES or level not in LEVELS:
            continue
        result = play(theme, level)
        while result == "new":
            result = play(theme, level)
        if result is None or input("Another? [y/N] ").strip().lower() != "y":
            return


def execute(args=None):
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
