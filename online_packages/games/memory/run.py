#!/usr/bin/env python3
"""Memory: turn over two cards at a time and find all the matching pairs in as few turns as you can.
Type two squares like  A1 C3  to flip them (or one at a time). Sizes: 4x4, 4x6 or 6x6."""
import random
import sys

from rich.console import Console
from rich.text import Text

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
SYMBOLS = ["@", "#", "$", "%", "&", "*", "+", "=", "?", "~", "^", "!", "<", ">", "/", "0", "1", "2"]
STYLES = ["red", "green", "yellow", "blue", "magenta", "cyan", "dark_orange", "bright_white", "pink1"]
SIZES = {"small": (4, 4), "medium": (4, 6), "large": (6, 6)}


class Game:
    def __init__(self, rows, cols, rng=None):
        rng = rng or random.Random()
        pairs = rows * cols // 2
        cards = SYMBOLS[:pairs] * 2
        rng.shuffle(cards)
        self.rows, self.cols = rows, cols
        self.cards = [cards[r * cols:(r + 1) * cols] for r in range(rows)]
        self.up = [[False] * cols for _ in range(rows)]
        self.turns = 0
        self.matched = 0

    def cell(self, text):
        text = text.strip().upper()
        if len(text) < 2 or not text[0].isalpha() or not text[1:].isdigit():
            return None
        c, r = ord(text[0]) - 65, int(text[1:]) - 1
        return (r, c) if 0 <= r < self.rows and 0 <= c < self.cols else None

    def flip_pair(self, a, b):
        """Turn two cards over. Returns True if they match (they then stay face up)."""
        self.turns += 1
        if self.cards[a[0]][a[1]] == self.cards[b[0]][b[1]]:
            self.up[a[0]][a[1]] = self.up[b[0]][b[1]] = True
            self.matched += 1
            return True
        return False

    def done(self):
        return self.matched == self.rows * self.cols // 2

    def render(self, showing=()):
        out = Text("    " + "  ".join(chr(65 + c) for c in range(self.cols)) + "\n", style="dim")
        for r in range(self.rows):
            out.append(f"{r + 1:>2}  ", style="dim")
            for c in range(self.cols):
                if self.up[r][c] or (r, c) in showing:
                    sym = self.cards[r][c]
                    style = STYLES[SYMBOLS.index(sym) % len(STYLES)]
                    out.append(f"{sym}  ", style=f"bold {style}" + (" reverse" if (r, c) in showing and not self.up[r][c] else ""))
                else:
                    out.append("?  ", style="dim")
            out.append("\n")
        return out


def play(size):
    game = Game(*SIZES[size])
    console.print(f"[bold]Memory[/bold] ({size}): flip two cards by typing two squares, like  A1 B2   (q to quit)")
    while not game.done():
        console.print(game.render(), end="")
        try:
            parts = input("flip> ").strip().replace(",", " ").split()
        except EOFError:
            return None
        if parts and parts[0].lower() in ("q", "quit"):
            return None
        if len(parts) == 1:
            try:
                parts.append(input("second card> ").strip())
            except EOFError:
                return None
        if len(parts) != 2:
            console.print("[yellow]Give two squares, like  A1 B2.[/yellow]")
            continue
        a, b = game.cell(parts[0]), game.cell(parts[1])
        if not a or not b or a == b or game.up[a[0]][a[1]] or game.up[b[0]][b[1]]:
            console.print("[yellow]Pick two different squares that are still face down.[/yellow]")
            continue
        console.print(game.render(showing={a, b}), end="")
        if game.flip_pair(a, b):
            console.print("[bold green]A match![/bold green]")
        else:
            console.print("[red]No match.[/red] [dim]Remember where they were. Press Enter...[/dim]")
            try:
                input()
            except EOFError:
                return None
            console.print("\n" * 3)
    console.print(game.render(), end="")
    console.print(f"[bold green]All pairs found in {game.turns} turns![/bold green]")
    return game.turns


def main():
    best = appdata.load("memory", {}) if appdata else {}
    while True:
        size = input("Size: small (4x4), medium (4x6), large (6x6), q to quit> ").strip().lower() or "small"
        if size == "q":
            return
        if size not in SIZES:
            continue
        turns = play(size)
        if turns is None:
            return
        if appdata and (size not in best or turns < best[size]):
            best[size] = turns
            appdata.save("memory", best)
            console.print(f"[bold yellow]New best for {size}: {turns} turns![/bold yellow]")
        elif size in best:
            console.print(f"[dim]Best for {size}: {best[size]} turns[/dim]")
        if input("Again? [y/N] ").strip().lower() != "y":
            return


def execute(args=None):
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
