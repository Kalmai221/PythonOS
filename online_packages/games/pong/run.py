#!/usr/bin/env python3
"""Pong against the computer: first to 7 wins. Real time where the terminal allows it: w/up and s/down move your paddle, q quits.
On devices without raw key input it switches to turn mode: type w or s (optionally with a number, like w3) to move your paddle, then Enter
lets the ball travel a few squares."""
import os
import random
import sys
import time

from rich.console import Console
from rich.live import Live
from rich.text import Text

console = Console()
W, H = 40, 16
PADDLE = 4
WIN = 7
LEVELS = {"easy": 0.55, "medium": 0.8, "hard": 0.95}                  # chance per frame that the computer follows the ball
ARROWS = {"H": "w", "P": "s", "A": "w", "B": "s"}


class Game:
    def __init__(self, level="medium", rng=None):
        self.rng = rng or random.Random()
        self.skill = LEVELS[level]
        self.left = self.right = (H - PADDLE) // 2         # paddle top rows: left is you, right is the computer
        self.you = self.cpu = 0
        self.serve(1)

    def serve(self, direction):
        self.bx, self.by = W / 2, H / 2
        self.vx = 0.8 * direction
        self.vy = self.rng.choice([-0.5, -0.3, 0.3, 0.5])

    def move_you(self, dy):
        self.left = max(0, min(H - PADDLE, self.left + dy))

    def step(self):
        """Advance the ball one frame and move the computer. Returns 'you', 'cpu' when someone scores, else None."""
        centre = self.right + PADDLE / 2
        if self.rng.random() < self.skill:
            if self.by < centre - 0.8:
                self.right = max(0, self.right - 1)
            elif self.by > centre + 0.8:
                self.right = min(H - PADDLE, self.right + 1)
        self.bx += self.vx
        self.by += self.vy
        if self.by < 0:
            self.by, self.vy = -self.by, -self.vy
        elif self.by > H - 1:
            self.by, self.vy = 2 * (H - 1) - self.by, -self.vy
        if self.bx <= 1 and self.vx < 0:                    # your side
            if self.left - 0.5 <= self.by <= self.left + PADDLE - 0.5:
                self.bounce(self.left)
            elif self.bx < 0:
                self.cpu += 1
                self.serve(1)
                return "cpu"
        elif self.bx >= W - 2 and self.vx > 0:              # the computer's side
            if self.right - 0.5 <= self.by <= self.right + PADDLE - 0.5:
                self.bounce(self.right)
            elif self.bx > W - 1:
                self.you += 1
                self.serve(-1)
                return "you"
        return None

    def bounce(self, paddle_top):
        """Reflect the ball; where it hits the paddle changes the angle, and it speeds up a little."""
        offset = (self.by - (paddle_top + PADDLE / 2)) / (PADDLE / 2)
        self.vx = -self.vx * 1.08 if abs(self.vx) < 2.2 else -self.vx
        self.vy = max(-1.0, min(1.0, offset * 0.8))
        self.bx = 1.5 if self.vx > 0 else W - 2.5

    def winner(self):
        return "you" if self.you >= WIN else "cpu" if self.cpu >= WIN else None


def render(game):
    out = Text(f" You {game.you}   Computer {game.cpu}   (first to {WIN})\n", style="bold")
    out.append("+" + "-" * W + "+\n", style="dim")
    for r in range(H):
        out.append("|", style="dim")
        for c in range(W):
            if c == 0 and game.left <= r < game.left + PADDLE:
                out.append("#", style="bold green")
            elif c == W - 1 and game.right <= r < game.right + PADDLE:
                out.append("#", style="bold red")
            elif int(round(game.bx)) == c and int(round(game.by)) == r:
                out.append("o", style="bold yellow")
            elif c == W // 2 and r % 2 == 0:
                out.append(":", style="dim")
            else:
                out.append(" ")
        out.append("|\n", style="dim")
    out.append("+" + "-" * W + "+\n", style="dim")
    return out


class Keys:
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


def play_real_time(keys, level):
    game = Game(level)
    with Live(render(game), console=console, auto_refresh=False) as live:
        while not game.winner():
            for key in keys.poll():
                if key == "q":
                    return None
                if key == "w":
                    game.move_you(-2)
                elif key == "s":
                    game.move_you(2)
            game.step()
            live.update(render(game), refresh=True)
            time.sleep(0.05)
    return game


def play_turns(level):
    game = Game(level)
    console.print("[dim]Turn mode: w/s move your paddle (w3 = three squares up); Enter moves the ball. q quits.[/dim]")
    while not game.winner():
        console.print(render(game), end="")
        try:
            text = input("paddle> ").strip().lower()
        except EOFError:
            return None
        if text == "q":
            return None
        if text[:1] in ("w", "s"):
            n = int(text[1:]) if text[1:].isdigit() else 2
            game.move_you(-n if text[0] == "w" else n)
        for _ in range(6):
            game.step()
    return game


def main():
    keys = Keys()
    try:
        while True:
            level = input("Level: easy, medium, hard (q to quit)> ").strip().lower() or "medium"
            if level == "q":
                return
            if level not in LEVELS:
                continue
            game = play_real_time(keys, level) if keys.real_time else play_turns(level)
            if keys.real_time:
                keys.close()
            if game is None:
                return
            console.print(f"[bold {'green' if game.winner() == 'you' else 'red'}]{'You win!' if game.winner() == 'you' else 'The computer wins.'}[/] {game.you} - {game.cpu}")
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
