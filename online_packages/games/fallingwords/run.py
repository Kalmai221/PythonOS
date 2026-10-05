#!/usr/bin/env python3
"""Falling words: words drift down the screen; type one and press Enter to zap it before it reaches the bottom. Three lives. The longer
you survive, the faster they fall. Real time where the terminal allows it; on devices without raw key input it plays in turns (every
line you type lets the words fall one row, so type quickly and carefully)."""
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
W, H = 44, 14
WORDS = """cat dog sun map key ice fox cup web bit app run fix log net pin zip bug code disk file link mail menu port root shell
screen kernel python folder window button cursor memory server script binary router laptop planet forest island bridge garden castle
market winter summer orange guitar coffee pencil rocket silver stream cloud river ocean tiger zebra eagle lemon honey cheese carrot
function variable network keyboard terminal compiler database package process program browser monitor library backup battery""".split()


class Game:
    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.words = []                      # dicts: text, x, y (float)
        self.lives, self.score, self.zapped = 3, 0, 0
        self.typed = ""
        self.since_spawn = 0.0
        self.elapsed = 0.0

    @property
    def level(self):
        return 1 + self.zapped // 8

    def speed(self):
        """Rows per second."""
        return 0.35 + 0.12 * (self.level - 1)

    def spawn(self):
        text = self.rng.choice([w for w in WORDS if all(w != x["text"] for x in self.words)])
        self.words.append({"text": text, "x": self.rng.randint(0, max(0, W - len(text) - 1)), "y": 0.0})

    def advance(self, dt):
        """Let time pass: words fall, new ones appear, words reaching the bottom cost a life."""
        self.elapsed += dt
        self.since_spawn += dt
        if self.since_spawn >= max(0.9, 2.4 - 0.15 * (self.level - 1)) or not self.words:
            self.spawn()
            self.since_spawn = 0.0
        for w in self.words:
            w["y"] += self.speed() * dt
        missed = [w for w in self.words if w["y"] >= H - 1]
        for w in missed:
            self.words.remove(w)
            self.lives -= 1
        return len(missed)

    def submit(self, text):
        """Try to zap the word `text`. Returns True if one was hit (the lowest matching word)."""
        text = text.strip().lower()
        matches = [w for w in self.words if w["text"] == text]
        if not matches:
            return False
        w = max(matches, key=lambda m: m["y"])
        self.words.remove(w)
        self.zapped += 1
        self.score += len(text) * 10 + max(0, int((H - w["y"]) * 2))
        return True

    @property
    def over(self):
        return self.lives <= 0


def render(game):
    rows = [[" "] * W for _ in range(H)]
    for w in game.words:
        y = int(w["y"])
        for i, ch in enumerate(w["text"]):
            if 0 <= y < H and 0 <= w["x"] + i < W:
                rows[y][w["x"] + i] = ch
    out = Text(f" Score {game.score}   Lives {'<3 ' * game.lives}  Level {game.level}\n", style="bold")
    out.append("+" + "-" * W + "+\n", style="dim")
    for r in range(H):
        out.append("|", style="dim")
        out.append("".join(rows[r]), style="bold red" if r >= H - 3 else "bold yellow" if r >= H - 6 else "white")
        out.append("|\n", style="dim")
    out.append("+" + "-" * W + "+\n", style="dim")
    out.append(f" > {game.typed}_\n", style="bold cyan")
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
        chars = []
        if os.name == "nt":
            import msvcrt
            while msvcrt.kbhit():
                chars.append(msvcrt.getwch())
        else:
            import select
            while select.select([sys.stdin], [], [], 0)[0]:
                chars.append(sys.stdin.read(1))
        return chars

    def close(self):
        if self._old is not None:
            import termios
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)


def play_real_time(keys):
    game = Game()
    last = time.time()
    with Live(render(game), console=console, auto_refresh=False) as live:
        while not game.over:
            for ch in keys.poll():
                if ch in ("\r", "\n"):
                    game.submit(game.typed)
                    game.typed = ""
                elif ch in ("\x08", "\x7f"):
                    game.typed = game.typed[:-1]
                elif ch == "\x1b" or ch == "\x03":
                    return game
                elif ch.isprintable():
                    game.typed += ch
            now = time.time()
            game.advance(now - last)
            last = now
            live.update(render(game), refresh=True)
            time.sleep(0.03)
    return game


def play_turns():
    game = Game()
    console.print("[dim]Turn mode: type a word you can see and press Enter; every line lets the words fall. 'q' quits.[/dim]")
    while not game.over:
        console.print(render(game), end="")
        try:
            text = input("zap> ").strip().lower()
        except EOFError:
            return game
        if text in ("q", "quit"):
            return game
        hit = game.submit(text)
        game.advance(1.2 if hit else 2.0)
    return game


def main():
    keys = Keys()
    best = appdata.load("fallingwords", {}).get("best", 0) if appdata else 0
    try:
        while True:
            game = play_real_time(keys) if keys.real_time else play_turns()
            if keys.real_time:
                keys.close()
            console.print(f"\n[bold]Game over.[/bold] Score {game.score}, {game.zapped} words zapped." + ("  [bold yellow]New best![/bold yellow]" if game.score > best else f"  Best {best}."))
            if game.score > best:
                best = game.score
                if appdata:
                    appdata.save("fallingwords", {"best": best})
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
