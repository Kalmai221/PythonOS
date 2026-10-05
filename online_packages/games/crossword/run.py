#!/usr/bin/env python3
"""Crossword: a new puzzle is built for you each time from a built-in list of words and clues, with the words interlocking on a grid.
Fill in answers with  3A hello  (answer for clue 3 across) or  5D river  (5 down). Commands: show, clues, hint 3A, check, reveal, new, q."""
import random
import sys

from rich.console import Console
from rich.text import Text

console = Console()

WORDS = {
    "python": "A popular programming language named after a comedy group", "kernel": "The core of an operating system",
    "shell": "Where you type commands", "folder": "A place to keep files together", "network": "Computers connected together",
    "memory": "Where running programs keep their data", "keyboard": "You type on it", "monitor": "A screen",
    "mouse": "A pointing device (and a small rodent)", "server": "A computer that serves others", "cloud": "Remote computers on the internet",
    "binary": "Numbers made of zeros and ones", "pixel": "One dot of a picture", "cursor": "The blinking marker where you type",
    "window": "A rectangular area on a screen", "bug": "A mistake in a program", "script": "A short program", "browser": "Shows web pages",
    "backup": "A spare copy of your files", "router": "Sends data between networks", "laptop": "A portable computer",
    "planet": "Mars or Venus", "river": "Flows to the sea", "ocean": "Very big body of salt water", "island": "Land surrounded by water",
    "forest": "Many trees together", "desert": "A very dry place", "mountain": "A very tall hill", "garden": "Where flowers grow",
    "winter": "The coldest season", "summer": "The warmest season", "orange": "A fruit and a colour", "banana": "A long yellow fruit",
    "bread": "Baked from flour", "cheese": "Made from milk", "pizza": "Round Italian dish with toppings", "coffee": "A hot morning drink",
    "guitar": "A stringed instrument", "piano": "It has black and white keys", "violin": "A small stringed instrument played with a bow",
    "castle": "A fortified home of a king", "bridge": "Crosses a river", "market": "Where goods are bought and sold",
}


class Puzzle:
    def __init__(self, size=15, rng=None, count=10):
        self.rng = rng or random.Random()
        self.size = size
        self.grid = {}                       # (r, c) -> letter
        self.entries = []                    # dicts: word, clue, r, c, across
        self.build(count)
        self.number()

    # ---------------------------------------------------------------- build
    def can_place(self, word, r, c, across):
        """Does the word fit at (r, c)? Letters may only cross where they match, and the word may not run alongside another."""
        dr, dc = (0, 1) if across else (1, 0)
        end_r, end_c = r + dr * (len(word) - 1), c + dc * (len(word) - 1)
        if not (0 <= r < self.size and 0 <= c < self.size and 0 <= end_r < self.size and 0 <= end_c < self.size):
            return False
        if (r - dr, c - dc) in self.grid or (end_r + dr, end_c + dc) in self.grid:
            return False
        crossings = 0
        for i, ch in enumerate(word):
            pos = (r + dr * i, c + dc * i)
            existing = self.grid.get(pos)
            if existing is not None:
                if existing != ch:
                    return False
                crossings += 1
            else:
                # the neighbours on either side must be empty, otherwise two words would run side by side
                for side in ((pos[0] + dc, pos[1] + dr), (pos[0] - dc, pos[1] - dr)):
                    if side in self.grid:
                        return False
        return crossings > 0 or not self.entries

    def place(self, word, r, c, across):
        dr, dc = (0, 1) if across else (1, 0)
        for i, ch in enumerate(word):
            self.grid[(r + dr * i, c + dc * i)] = ch
        self.entries.append({"word": word, "clue": WORDS[word], "r": r, "c": c, "across": across})

    def build(self, count):
        words = list(WORDS)
        self.rng.shuffle(words)
        words.sort(key=len, reverse=True)
        first = words.pop(0)
        self.place(first, self.size // 2, max(0, (self.size - len(first)) // 2), True)
        attempts = 0
        while len(self.entries) < count and words and attempts < 400:
            attempts += 1
            word = words.pop(0) if self.rng.random() < 0.5 else words.pop(self.rng.randrange(len(words)))
            options = []
            for e in self.entries:
                for i, ch in enumerate(word):
                    for j, ch2 in enumerate(e["word"]):
                        if ch == ch2:
                            if e["across"]:           # the new word goes down through letter j of e
                                options.append((e["r"] - i, e["c"] + j, False))
                            else:
                                options.append((e["r"] + j, e["c"] - i, True))
            self.rng.shuffle(options)
            for r, c, across in options:
                if self.can_place(word, r, c, across):
                    self.place(word, r, c, across)
                    break
            else:
                if attempts < 200:
                    words.append(word)

    def number(self):
        """Clue numbers go left to right, top to bottom, shared by an across and a down word starting on the same square."""
        starts = sorted({(e["r"], e["c"]) for e in self.entries})
        self.numbers = {pos: i for i, pos in enumerate(starts, 1)}
        for e in self.entries:
            e["n"] = self.numbers[(e["r"], e["c"])]
        self.entries.sort(key=lambda e: (e["n"], not e["across"]))
        self.answers = {}
        self.filled = {}

    # ----------------------------------------------------------------- play
    def find(self, label):
        label = label.strip().upper()
        if len(label) < 2 or label[-1] not in "AD" or not label[:-1].isdigit():
            return None
        n, across = int(label[:-1]), label[-1] == "A"
        for e in self.entries:
            if e["n"] == n and e["across"] == across:
                return e
        return None

    def cells(self, e):
        dr, dc = (0, 1) if e["across"] else (1, 0)
        return [(e["r"] + dr * i, e["c"] + dc * i) for i in range(len(e["word"]))]

    def fill(self, e, answer):
        """Write an answer into the grid. Returns True if it is the right word."""
        answer = answer.strip().lower()
        if len(answer) != len(e["word"]):
            return False
        for pos, ch in zip(self.cells(e), answer):
            self.filled[pos] = ch
        return answer == e["word"]

    def correct(self):
        return all(self.filled.get(p) == ch for p, ch in self.grid.items())

    def render(self, reveal=False):
        rows = [r for r, _ in self.grid]
        cols = [c for _, c in self.grid]
        r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
        out = Text()
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if (r, c) not in self.grid:
                    out.append("   ", style="on grey11")
                    continue
                num = self.numbers.get((r, c))
                ch = self.grid[(r, c)] if reveal else self.filled.get((r, c))
                label = f"{num}" if num else ""
                if label:
                    out.append(f"{label:<2}", style="dim")
                    out.append((ch or "_").upper(), style="bold cyan" if ch else "white")
                else:
                    out.append(f" {(ch or '_').upper()} ", style="bold cyan" if ch else "white")
            out.append("\n")
        return out

    def clue_text(self):
        lines = ["Across:"] + [f"  {e['n']}A ({len(e['word'])}) {e['clue']}" for e in self.entries if e["across"]]
        lines += ["Down:"] + [f"  {e['n']}D ({len(e['word'])}) {e['clue']}" for e in self.entries if not e["across"]]
        return "\n".join(lines)


def play():
    puzzle = Puzzle()
    console.print("[bold]Crossword[/bold]  3A hello = answer 3 across. Commands: show, clues, hint 3A, check, reveal, new, q.")
    while True:
        console.print(puzzle.render(), end="")
        console.print(puzzle.clue_text(), markup=False)
        while True:
            if puzzle.correct():
                console.print("[bold green]Solved! Every word is right.[/bold green]")
                return True
            try:
                parts = input("> ").strip().split(None, 1)
            except EOFError:
                return None
            if not parts:
                continue
            cmd = parts[0].lower()
            if cmd in ("q", "quit"):
                return None
            if cmd == "new":
                return "new"
            if cmd == "show":
                console.print(puzzle.render(), end="")
            elif cmd == "clues":
                console.print(puzzle.clue_text(), markup=False)
            elif cmd == "check":
                wrong = [e for e in puzzle.entries if any(puzzle.filled.get(p) not in (None, ch) for p, ch in zip(puzzle.cells(e), e["word"]))]
                console.print("[green]Nothing wrong so far.[/green]" if not wrong else "[yellow]Check: " + ", ".join(f"{e['n']}{'A' if e['across'] else 'D'}" for e in wrong) + "[/yellow]")
            elif cmd == "reveal":
                console.print(puzzle.render(reveal=True), end="")
                return False
            elif cmd == "hint" and len(parts) > 1:
                e = puzzle.find(parts[1])
                if not e:
                    console.print("[yellow]No such clue.[/yellow]")
                    continue
                for pos, ch in zip(puzzle.cells(e), e["word"]):
                    if puzzle.filled.get(pos) != ch:
                        puzzle.filled[pos] = ch
                        break
                console.print(puzzle.render(), end="")
            else:
                e = puzzle.find(cmd)
                if e and len(parts) > 1:
                    if len(parts[1].strip()) != len(e["word"]):
                        console.print(f"[yellow]That answer has {len(e['word'])} letters.[/yellow]")
                    else:
                        right = puzzle.fill(e, parts[1])
                        console.print("[green]Fits![/green]" if right else "[red]Written in, but check it.[/red]")
                        console.print(puzzle.render(), end="")
                else:
                    console.print("[yellow]Try  3A hello  or  hint 3A.[/yellow]")


def main():
    while True:
        result = play()
        if result == "new":
            continue
        if result is None or input("Another puzzle? [y/N] ").strip().lower() != "y":
            return


def execute(args=None):
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
