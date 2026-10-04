#!/usr/bin/env python3
"""Snake. Real-time with the arrow keys or WASD where the terminal allows it; on devices without raw key input
(such as the Android app) it switches to turn mode: type w/a/s/d and Enter to move, Enter alone to keep going."""
import json
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
W, H = 30, 16
DIRS = {"w": (0, -1), "s": (0, 1), "a": (-1, 0), "d": (1, 0)}
ARROWS = {"H": "w", "P": "s", "K": "a", "M": "d", "A": "w", "B": "s", "D": "a", "C": "d"}   # Windows / ANSI arrow codes


def high_score():
    return (appdata.load("snake", {}) if appdata else {}).get("best", 0)


def save_high(score):
    if appdata and score > high_score():
        appdata.save("snake", {"best": score})


# ----------------------------------------------------------------- keys
class Keys:
    """Non-blocking single-key reader. `real_time` is False when the terminal cannot do it."""

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
        """The newest pending key as w/a/s/d/q (or None)."""
        key = None
        if os.name == "nt":
            import msvcrt
            while msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):
                    ch = ARROWS.get(msvcrt.getwch(), "")
                key = ch.lower() or key
        else:
            import select
            while select.select([sys.stdin], [], [], 0)[0]:
                ch = sys.stdin.read(1)
                if ch == "\x1b" and select.select([sys.stdin], [], [], 0.01)[0]:
                    sys.stdin.read(1)
                    ch = ARROWS.get(sys.stdin.read(1), "")
                key = ch.lower() or key
        return key

    def close(self):
        if self._old is not None:
            import termios
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)


# ----------------------------------------------------------------- game
def new_food(snake):
    free = [(x, y) for x in range(W) for y in range(H) if (x, y) not in snake]
    return random.choice(free) if free else None


def step(snake, direction, food):
    """Advance one move. Returns (alive, ate)."""
    head = (snake[0][0] + direction[0], snake[0][1] + direction[1])
    ate = head == food
    body = snake if ate else snake[:-1]
    if not (0 <= head[0] < W and 0 <= head[1] < H) or head in body:
        return False, False
    snake.insert(0, head)
    if not ate:
        snake.pop()
    return True, ate


def render(snake, food, score, best):
    rows = [Text(f" Snake   score {score}   best {max(best, score)}   (q quits)", style="bold")]
    rows.append(Text("+" + "-" * W + "+", style="dim"))
    for y in range(H):
        line = Text("|", style="dim")
        for x in range(W):
            if (x, y) == snake[0]:
                line.append("@", style="bold green")
            elif (x, y) in snake:
                line.append("o", style="green")
            elif (x, y) == food:
                line.append("*", style="bold red")
            else:
                line.append(" ")
        line.append("|", style="dim")
        rows.append(line)
    rows.append(Text("+" + "-" * W + "+", style="dim"))
    return Text("\n").join(rows)


def play_real_time(keys):
    snake = [(W // 2, H // 2), (W // 2 - 1, H // 2), (W // 2 - 2, H // 2)]
    direction, food, score, best = (1, 0), new_food(snake), 0, high_score()
    delay = 0.14
    with Live(render(snake, food, score, best), console=console, auto_refresh=False, transient=False) as live:
        while True:
            end = time.time() + delay
            while time.time() < end:
                key = keys.poll()
                if key == "q":
                    return score
                if key in DIRS:
                    new = DIRS[key]
                    if (new[0] != -direction[0] or new[1] != -direction[1]):
                        direction = new
                time.sleep(0.01)
            alive, ate = step(snake, direction, food)
            if not alive:
                return score
            if ate:
                score += 1
                delay = max(0.05, delay - 0.004)
                food = new_food(snake)
                if food is None:
                    return score
            live.update(render(snake, food, score, best), refresh=True)


def play_turns():
    snake = [(W // 2, H // 2), (W // 2 - 1, H // 2), (W // 2 - 2, H // 2)]
    direction, food, score, best = (1, 0), new_food(snake), 0, high_score()
    console.print("[dim]Turn mode: w/a/s/d + Enter to turn, Enter to move on, a number first (like 4d) moves several steps, q to quit.[/dim]")
    while True:
        console.print(render(snake, food, score, best))
        try:
            text = input("move> ").strip().lower()
        except EOFError:
            return score
        if text == "q":
            return score
        count, turn = 1, text
        if text[:1].isdigit():
            digits = "".join(ch for ch in text if ch.isdigit())
            count, turn = max(1, min(int(digits), 10)), text[len(digits):]
        if turn[:1] in DIRS:
            new = DIRS[turn[:1]]
            if (new[0] != -direction[0] or new[1] != -direction[1]):
                direction = new
        for _ in range(count):
            alive, ate = step(snake, direction, food)
            if not alive:
                return score
            if ate:
                score += 1
                food = new_food(snake)
                if food is None:
                    return score


def main():
    keys = Keys()
    try:
        while True:
            score = play_real_time(keys) if keys.real_time else play_turns()
            new_best = score > high_score()
            save_high(score)
            console.print(f"\n[bold red]Game over![/bold red] You scored [bold]{score}[/bold]." + ("  [bold yellow]New best![/bold yellow]" if new_best and score else ""))
            if keys.real_time:
                keys.close()
            answer = input("Play again? [y/N] ").strip().lower()
            if answer != "y":
                return
            if keys.real_time:
                keys = Keys()
    finally:
        keys.close()


def execute():
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute()
