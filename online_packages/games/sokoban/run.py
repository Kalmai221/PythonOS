#!/usr/bin/env python3
"""Sokoban: push every box ($) onto a goal (.) from the warehouse worker (@). You can push one box at a time and never pull.

Type moves with w a s d (several in a row are fine: ddwa), u to undo, r to restart the level, n to skip to the next level, q to quit.
"""
import sys

from rich.console import Console
from rich.text import Text

console = Console()

# # wall, space floor, $ box, . goal, @ worker, * box on goal, + worker on goal
LEVELS = [
    ["#####",
     "#@$.#",
     "#####"],
    ["######",
     "#    #",
     "# $$ #",
     "# .. #",
     "#  @ #",
     "######"],
    ["####",
     "# .#",
     "#  ###",
     "#*@  #",
     "#  $ #",
     "#  ###",
     "####"],
    ["######",
     "#    #",
     "# #@ #",
     "# $* #",
     "# .* #",
     "#    #",
     "######"],
    ["  ####",
     "###  ####",
     "#     $ #",
     "# #  #$ #",
     "# . .#@ #",
     "#########"],
]
MOVES = {"w": (0, -1), "a": (-1, 0), "s": (0, 1), "d": (1, 0)}


class Level:
    def __init__(self, rows):
        self.walls, self.goals, self.boxes = set(), set(), set()
        self.player = (0, 0)
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "#":
                    self.walls.add((x, y))
                if ch in ".*+":
                    self.goals.add((x, y))
                if ch in "$*":
                    self.boxes.add((x, y))
                if ch in "@+":
                    self.player = (x, y)
        self.width = max(len(r) for r in rows)
        self.height = len(rows)
        self.history = []
        self.moves = 0

    def move(self, key):
        """Try a step. Returns True when the worker moved (pushing a box if there was one)."""
        dx, dy = MOVES[key]
        x, y = self.player
        target = (x + dx, y + dy)
        if target in self.walls:
            return False
        pushed = None
        if target in self.boxes:
            beyond = (target[0] + dx, target[1] + dy)
            if beyond in self.walls or beyond in self.boxes:
                return False
            pushed = (target, beyond)
        self.history.append((self.player, pushed))
        if pushed:
            self.boxes.remove(pushed[0])
            self.boxes.add(pushed[1])
        self.player = target
        self.moves += 1
        return True

    def undo(self):
        if not self.history:
            return False
        player, pushed = self.history.pop()
        if pushed:
            self.boxes.remove(pushed[1])
            self.boxes.add(pushed[0])
        self.player = player
        self.moves -= 1
        return True

    def solved(self):
        return self.boxes == self.goals

    def render(self):
        text = Text()
        for y in range(self.height):
            for x in range(self.width):
                cell = (x, y)
                if cell in self.walls:
                    text.append("##", style="grey50")
                elif cell == self.player:
                    text.append("@ ", style="bold yellow")
                elif cell in self.boxes:
                    text.append("[]", style="bold green" if cell in self.goals else "bold red")
                elif cell in self.goals:
                    text.append(". ", style="cyan")
                else:
                    text.append("  ")
            text.append("\n")
        return text


def play(number):
    level = Level(LEVELS[number])
    while True:
        console.print(f"\n[bold]Level {number + 1} of {len(LEVELS)}[/bold]   moves: {level.moves}")
        console.print(level.render())
        if level.solved():
            console.print(f"[bold green]Solved in {level.moves} moves![/bold green]")
            return "next"
        try:
            line = console.input("w a s d, (u)ndo (r)estart (n)ext (q)uit > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "quit"
        for ch in line:
            if ch in MOVES:
                level.move(ch)
            elif ch == "u":
                level.undo()
            elif ch == "r":
                level = Level(LEVELS[number])
            elif ch == "n":
                return "next"
            elif ch == "q":
                return "quit"
            if level.solved():
                break


def execute(args=None):
    number = 0
    if args and args[0].isdigit() and 1 <= int(args[0]) <= len(LEVELS):
        number = int(args[0]) - 1
    while number < len(LEVELS):
        if play(number) == "quit":
            return True
        number += 1
    console.print("[bold green]You finished every level. Well done![/bold green]")
    return True


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
