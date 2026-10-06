#!/usr/bin/env python3
"""Tetris. Real time where the terminal allows it: a/left and d/right move, w/up rotates, s/down drops one row, space drops all the way,
q quits. On devices without raw key input (such as the Android app) it switches to turn mode: type moves like  a a w x  (x = hard drop)
and press Enter; the piece also falls one row after each line you type."""
import os
import random
import sys
import time

from rich.console import Console
from rich.live import Live
from rich.text import Text

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
W, H = 10, 20
SHAPES = {
    "I": [[(0, 1), (1, 1), (2, 1), (3, 1)], [(2, 0), (2, 1), (2, 2), (2, 3)], [(0, 2), (1, 2), (2, 2), (3, 2)], [(1, 0), (1, 1), (1, 2), (1, 3)]],
    "O": [[(1, 0), (2, 0), (1, 1), (2, 1)]] * 4,
    "T": [[(1, 0), (0, 1), (1, 1), (2, 1)], [(1, 0), (1, 1), (2, 1), (1, 2)], [(0, 1), (1, 1), (2, 1), (1, 2)], [(1, 0), (0, 1), (1, 1), (1, 2)]],
    "S": [[(1, 0), (2, 0), (0, 1), (1, 1)], [(1, 0), (1, 1), (2, 1), (2, 2)], [(1, 1), (2, 1), (0, 2), (1, 2)], [(0, 0), (0, 1), (1, 1), (1, 2)]],
    "Z": [[(0, 0), (1, 0), (1, 1), (2, 1)], [(2, 0), (1, 1), (2, 1), (1, 2)], [(0, 1), (1, 1), (1, 2), (2, 2)], [(1, 0), (0, 1), (1, 1), (0, 2)]],
    "J": [[(0, 0), (0, 1), (1, 1), (2, 1)], [(1, 0), (2, 0), (1, 1), (1, 2)], [(0, 1), (1, 1), (2, 1), (2, 2)], [(1, 0), (1, 1), (0, 2), (1, 2)]],
    "L": [[(2, 0), (0, 1), (1, 1), (2, 1)], [(1, 0), (1, 1), (1, 2), (2, 2)], [(0, 1), (1, 1), (2, 1), (0, 2)], [(0, 0), (1, 0), (1, 1), (1, 2)]],
}
STYLE = {"I": "cyan", "O": "yellow", "T": "magenta", "S": "green", "Z": "red", "J": "blue", "L": "dark_orange"}
POINTS = {0: 0, 1: 100, 2: 300, 3: 500, 4: 800}
ARROWS = {"H": "w", "P": "s", "K": "a", "M": "d", "A": "w", "B": "s", "D": "a", "C": "d"}


class Game:
    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.grid = [[None] * W for _ in range(H)]
        self.score, self.lines, self.over = 0, 0, False
        self.bag = []
        self.next_kind = self.draw()
        self.spawn()

    @property
    def level(self):
        return self.lines // 10 + 1

    def draw(self):
        """Pieces come out of a shuffled bag of seven, so you never wait long for any shape."""
        if not self.bag:
            self.bag = list(SHAPES)
            self.rng.shuffle(self.bag)
        return self.bag.pop()

    def cells(self, kind=None, rot=None, x=None, y=None):
        kind, rot = kind or self.kind, self.rot if rot is None else rot
        x, y = self.x if x is None else x, self.y if y is None else y
        return [(x + cx, y + cy) for cx, cy in SHAPES[kind][rot % 4]]

    def fits(self, cells):
        return all(0 <= cx < W and cy < H and (cy < 0 or self.grid[cy][cx] is None) for cx, cy in cells)

    def spawn(self):
        self.kind, self.next_kind = self.next_kind, self.draw()
        self.rot, self.x, self.y = 0, 3, -1
        if not self.fits(self.cells()):
            self.over = True

    def move(self, dx):
        if self.fits(self.cells(x=self.x + dx)):
            self.x += dx
            return True
        return False

    def rotate(self):
        for kick in (0, -1, 1, -2, 2):                  # try to nudge the piece sideways if it does not fit after turning
            if self.fits(self.cells(rot=self.rot + 1, x=self.x + kick)):
                self.rot += 1
                self.x += kick
                return True
        return False

    def lock(self):
        for cx, cy in self.cells():
            if cy < 0:
                self.over = True
            else:
                self.grid[cy][cx] = self.kind
        cleared = [r for r in range(H) if all(self.grid[r])]
        for r in cleared:
            del self.grid[r]
            self.grid.insert(0, [None] * W)
        self.lines += len(cleared)
        self.score += POINTS[len(cleared)] * self.level
        if not self.over:
            self.spawn()
        return len(cleared)

    def tick(self):
        """Gravity: move down one row, or lock the piece if it cannot. Returns True if it locked."""
        if self.fits(self.cells(y=self.y + 1)):
            self.y += 1
            return False
        self.lock()
        return True

    def hard_drop(self):
        distance = 0
        while self.fits(self.cells(y=self.y + 1)):
            self.y += 1
            distance += 1
        self.score += distance * 2
        self.lock()

    def ghost_y(self):
        y = self.y
        while self.fits(self.cells(y=y + 1)):
            y += 1
        return y

    def delay(self):
        return max(0.08, 0.7 - (self.level - 1) * 0.06)


def render(game):
    shown = {c: game.kind for c in game.cells()}
    ghost = {c for c in game.cells(y=game.ghost_y())} if not game.over else set()
    out = Text()
    for r in range(H):
        out.append("|", style="dim")
        for c in range(W):
            kind = game.grid[r][c] or shown.get((c, r))
            if kind:
                out.append("[]", style=f"bold {STYLE[kind]}")
            elif (c, r) in ghost:
                out.append("..", style="dim")
            else:
                out.append("  ")
        out.append("|")
        if r == 0:
            out.append(f"  Score {game.score}", style="bold")
        elif r == 1:
            out.append(f"  Lines {game.lines}   Level {game.level}", style="dim")
        elif r == 3:
            out.append("  Next:", style="dim")
        elif 4 <= r <= 5:
            row = r - 4
            out.append("  ")
            for cx in range(4):
                out.append("[]" if (cx, row) in SHAPES[game.next_kind][0] else "  ", style=STYLE[game.next_kind])
        out.append("\n")
    out.append("+" + "--" * W + "+\n", style="dim")
    return out


class Keys:
    """Non-blocking single-key reader (see the Snake app). real_time is False when the terminal cannot do it."""

    def __init__(self):
        self.real_time = sys.stdin.isatty() and sys.stdout.isatty()
        self._old = None
        if not self.real_time:
            return
        if os.name == "nt":
            try:
                import msvcrt  # noqa: F401
            except ImportError:
                self.real_time = False
        else:
            try:
                import termios
                import tty
                self._fd = sys.stdin.fileno()
                self._old = termios.tcgetattr(self._fd)
                tty.setcbreak(self._fd)
            except Exception:
                self.real_time = False

    def poll(self):
        keys = []
        if os.name == "nt":
            import msvcrt
            while msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):
                    ch = ARROWS.get(msvcrt.getwch(), "")
                keys.append(ch.lower())
        else:
            import select
            while select.select([sys.stdin], [], [], 0)[0]:
                ch = sys.stdin.read(1)
                if ch == "\x1b" and select.select([sys.stdin], [], [], 0.01)[0]:
                    sys.stdin.read(1)
                    ch = ARROWS.get(sys.stdin.read(1), "")
                keys.append(ch.lower())
        return [k for k in keys if k]

    def close(self):
        if self._old is not None:
            import termios
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)


def handle(game, key):
    """Apply one key. Returns 'quit' to leave."""
    if key == "q":
        return "quit"
    if key in ("a", "j"):
        game.move(-1)
    elif key in ("d", "l"):
        game.move(1)
    elif key in ("w", "k"):
        game.rotate()
    elif key in ("s",):
        if not game.tick():
            game.score += 1
    elif key in (" ", "x"):
        game.hard_drop()
    return None


def play_real_time(keys):
    game = Game()
    last = time.time()
    with Live(render(game), console=console, auto_refresh=False) as live:
        while not game.over:
            for key in keys.poll():
                if handle(game, key) == "quit":
                    return game
            if time.time() - last >= game.delay():
                game.tick()
                last = time.time()
            live.update(render(game), refresh=True)
            time.sleep(0.02)
    return game


def play_turns():
    game = Game()
    console.print("[dim]Turn mode: a=left d=right w=rotate s=down x=drop; several per line (like  a a w x). Enter alone = down. q = quit.[/dim]")
    while not game.over:
        console.print(render(game), end="")
        try:
            line = input("moves> ").strip().lower()
        except EOFError:
            return game
        if line in ("q", "quit"):
            return game
        for key in (line.replace(" ", "") or "s"):
            if handle(game, key) == "quit" or game.over:
                break
        if not game.over:
            game.tick()
    return game


def main():
    keys = Keys()
    best = appdata.load("tetris", {}).get("best", 0) if appdata else 0
    try:
        while True:
            game = play_real_time(keys) if keys.real_time else play_turns()
            if keys.real_time:
                keys.close()
            console.print(f"\n[bold red]Game over.[/bold red] Score {game.score}, {game.lines} lines." + ("  [bold yellow]New best![/bold yellow]" if game.score > best else ""))
            if game.score > best:
                best = game.score
                if appdata:
                    appdata.save("tetris", {"best": best})
            if input("Play again? [y/N] ").strip().lower() != "y":
                return
            if keys.real_time:
                keys = Keys()
    finally:
        keys.close()


def execute(args=None):
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
