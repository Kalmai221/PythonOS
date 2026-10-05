#!/usr/bin/env python3
"""Typing test: type the text as fast and accurately as you can. Modes: timed (15, 30 or 60 seconds of words), a fixed number of words,
punctuation and capitals, code, famous quotes, or your own text from a file. With a real keyboard you see your accuracy live as you type;
on devices without raw key input it works one line at a time. Reports words per minute and accuracy, saves every result and draws your
progress. Usage: typingtest [15|30|60|words|punct|code|quote|file <path>|stats]"""
import difflib
import os
import random
import sys
import time

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

try:
    from pyos import appdata, fs
except ImportError:
    appdata = fs = None

console = Console()

COMMON = """the be to of and a in that have it for not on with he as you do at this but his by from they we say her she or an will
my one all would there their what so up out if about who get which go me when make can like time no just him know take people
into year your good some could them see other than then now look only come its over think also back after use two how our work
first well way even new want because any these give day most us system file open run home folder time text word line screen
key type fast quick brown fox jumps lazy dog simple clear small large bright dark light water stone river cloud green music
paper pencil window garden market bridge forest mirror silver ocean planet rocket button memory shell kernel python network""".split()
SENTENCES = [
    "The quick brown fox jumps over the lazy dog.",
    "Pack my box with five dozen liquor jugs.",
    "Sphinx of black quartz, judge my vow.",
    "A journey of a thousand miles begins with a single step.",
    "Programs must be written for people to read, and only incidentally for machines to execute.",
    "Simple is better than complex. Complex is better than complicated.",
    "Readability counts. Special cases are not special enough to break the rules.",
]
QUOTES = [
    "It always seems impossible until it is done.",
    "The only way to do great work is to love what you do.",
    "Well done is better than well said.",
    "Whether you think you can, or you think you can't, you're right.",
    "In the middle of difficulty lies opportunity.",
    "Do not go where the path may lead; go instead where there is no path and leave a trail.",
    "The best time to plant a tree was twenty years ago. The second best time is now.",
]
CODE = [
    "for i in range(10): print(i * 2)",
    "def add(a, b): return a + b",
    "if x > 0 and y < 10: total += x * y",
    "items = [n ** 2 for n in range(5) if n % 2 == 0]",
    "with open('notes.txt') as f: lines = f.readlines()",
    "result = {'name': 'pyOS', 'version': (1, 0, 2)}",
    "while not done: queue.append(data[idx]); idx += 1",
    "print(f'{name}: {value:.2f} ({count}/{total})')",
]
PUNCT_ONLY = ["Hello,", "world!", "it's", "don't", "\"quoted\"", "(brackets)", "end.", "yes;", "no:", "well-known", "Python", "February", "okay?", "first,", "done."]
PUNCT_WORDS = COMMON + PUNCT_ONLY
MODES = {"15": 15, "30": 30, "60": 60}
ARROWS = {"H": "", "P": "", "K": "", "M": ""}


def make_text(mode, words=40, rng=None):
    rng = rng or random
    if mode in MODES or mode == "words":
        return " ".join(rng.choice(COMMON) for _ in range(words if mode == "words" else 150))
    if mode == "punct":
        out, capital = [], True
        for i in range(35):
            w = rng.choice(PUNCT_ONLY) if i % 4 == 3 else rng.choice(COMMON)
            out.append(w.capitalize() if capital and w[0].islower() else w)
            capital = w.endswith((".", "!", "?"))
        return " ".join(out)
    if mode == "code":
        return rng.choice(CODE)
    if mode == "quote":
        return rng.choice(QUOTES + SENTENCES)
    raise ValueError(mode)


def score(target, typed, seconds):
    """(wpm, accuracy %, correct characters). A 'word' is five characters, the usual convention."""
    matcher = difflib.SequenceMatcher(None, target, typed, autojunk=False)
    correct = sum(block.size for block in matcher.get_matching_blocks())
    accuracy = 100 * correct / max(len(typed), 1) if typed else 0.0
    wpm = (correct / 5) / max(seconds / 60, 1 / 600)
    return wpm, min(100.0, accuracy), correct


def live_accuracy(target, typed):
    """Characters typed so far that are right, position by position (what you see as you type)."""
    right = sum(1 for a, b in zip(target, typed) if a == b)
    return 100 * right / len(typed) if typed else 100.0


def marked(target, typed):
    out = Text()
    for i, ch in enumerate(target):
        if i < len(typed):
            out.append(ch, style="green" if typed[i] == ch else "bold white on red")
        elif i == len(typed):
            out.append(ch, style="reverse")
        else:
            out.append(ch, style="dim")
    return out


def diff_marked(target, typed):
    out = Text()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, target, typed, autojunk=False).get_opcodes():
        if tag == "equal":
            out.append(target[i1:i2], style="green")
        elif tag in ("replace", "delete"):
            out.append(target[i1:i2], style="bold red underline")
    return out


# ---------------------------------------------------------------- history
def load():
    return appdata.load("typingtest", {"best": {}, "tests": 0, "history": []}) if appdata else {"best": {}, "tests": 0, "history": []}


def save_result(mode, wpm, accuracy, seconds):
    data = load()
    data.setdefault("best", {})
    if isinstance(data["best"], int):
        data["best"] = {}
    data["tests"] = data.get("tests", 0) + 1
    new_best = False
    if accuracy >= 90 and wpm > data["best"].get(mode, 0):
        data["best"][mode] = round(wpm)
        new_best = True
    data["history"] = (data.get("history", []) + [{"t": int(time.time()), "mode": mode, "wpm": round(wpm), "acc": round(accuracy), "sec": round(seconds)}])[-200:]
    if appdata:
        appdata.save("typingtest", data)
    return new_best, data


def spark(values, lo=None, hi=None):
    chars = " .:-=+*#"
    lo = min(values) if lo is None else lo
    hi = max(values) if hi is None else hi
    span = max(hi - lo, 1)
    return "".join(chars[min(len(chars) - 1, int((v - lo) / span * (len(chars) - 1)))] for v in values)


def stats():
    data = load()
    history = data.get("history", [])
    if not history:
        console.print("[dim]No tests yet. Run: typingtest[/dim]")
        return
    wpms = [h["wpm"] for h in history]
    console.print(f"[bold]{len(history)} test(s)[/bold]   average {sum(wpms) / len(wpms):.0f} WPM   best {max(wpms)} WPM   "
                  f"average accuracy {sum(h['acc'] for h in history) / len(history):.0f}%")
    last = wpms[-40:]
    top = max(last)
    console.print("\nSpeed over your last tests (WPM):")
    for level in range(6, 0, -1):
        threshold = top * (level - 0.5) / 6
        console.print(f"{top * level / 6:5.0f} |" + "".join("#" if v >= threshold else " " for v in last), markup=False)
    console.print("      +" + "-" * len(last), markup=False)
    table = Table(header_style="bold blue", title="Best by mode (90%+ accuracy)")
    table.add_column("Mode")
    table.add_column("WPM", justify="right")
    best = data.get("best", {})
    for mode, value in sorted(best.items()) if isinstance(best, dict) else []:
        table.add_row(mode, str(value))
    console.print(table)
    recent = Table(header_style="bold blue", title="Latest")
    for col in ("When", "Mode", "WPM", "Accuracy"):
        recent.add_column(col)
    for h in history[-8:]:
        recent.add_row(time.strftime("%d %b %H:%M", time.localtime(h["t"])), h["mode"], str(h["wpm"]), f"{h['acc']}%")
    console.print(recent)


# ------------------------------------------------------------------- keys
class Keys:
    """Non-blocking key reader; real_time is False when the terminal cannot do it (then tests are typed a line at a time)."""

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
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):
                    msvcrt.getwch()
                    continue
                chars.append(ch)
        else:
            import select
            while select.select([sys.stdin], [], [], 0)[0]:
                chars.append(sys.stdin.read(1))
        return chars

    def close(self):
        if self._old is not None:
            import termios
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)


def panel(target, typed, elapsed, limit, started):
    wpm, _acc, _c = score(target, typed, max(elapsed, 1)) if started else (0, 100, 0)
    head = Text(f"Time {max(0, limit - elapsed):4.1f}s   " if limit else f"Time {elapsed:4.1f}s   ", style="bold")
    head.append(f"{wpm:3.0f} WPM   ", style="cyan")
    head.append(f"accuracy {live_accuracy(target, typed):3.0f}%", style="green" if live_accuracy(target, typed) >= 95 else "yellow")
    return Panel(Text("\n").join([head, marked(target[:400], typed[:400])]), title="Type this - Esc to stop", border_style="blue")


def run_real_time(keys, target, limit):
    """Type against the clock (limit seconds, or 0 for no limit: the test ends when the whole text is typed). Returns (typed, seconds)."""
    typed, start = "", None
    with Live(panel(target, typed, 0, limit, False), console=console, auto_refresh=False) as live:
        while True:
            for ch in keys.poll():
                if start is None and ch.isprintable():
                    start = time.time()
                if ch in ("\x1b", "\x03"):
                    return typed, (time.time() - start) if start else 0
                if ch in ("\x08", "\x7f"):
                    typed = typed[:-1]
                elif ch in ("\r", "\n"):
                    continue
                elif ch.isprintable():
                    typed += ch
            elapsed = (time.time() - start) if start else 0
            live.update(panel(target, typed, elapsed, limit, start is not None), refresh=True)
            if (limit and start and elapsed >= limit) or (not limit and len(typed) >= len(target)):
                return typed, min(elapsed, limit) if limit else elapsed
            time.sleep(0.03)


def run_lines(target, limit):
    console.print(Panel(target[:600], title="Type this", border_style="blue"))
    input("Press Enter, then type the text and press Enter when you finish... ")
    console.print("[bold green]Go![/bold green]")
    start = time.time()
    typed = input("> ")
    return typed, time.time() - start


def run_test(mode, keys, custom=None):
    limit = MODES.get(mode, 0)
    target = custom if custom is not None else make_text(mode)
    if keys.real_time:
        console.print(f"[bold]{'Timed ' + str(limit) + ' s' if limit else mode}[/bold]  - the clock starts at your first key.")
        typed, seconds = run_real_time(keys, target, limit)
        keys.close()
    else:
        typed, seconds = run_lines(target, limit)
    if not typed:
        console.print("[yellow]Nothing typed.[/yellow]")
        return
    wpm, accuracy, _ = score(target[:len(typed)] if limit or keys.real_time else target, typed, seconds)
    console.print(Panel(diff_marked(target[:len(typed)] if (limit or keys.real_time) else target, typed),
                        title="Your text vs the target (red = wrong or missed)", border_style="blue"))
    table = Table(show_header=False, box=None)
    table.add_row("Speed", f"[bold cyan]{wpm:.0f} WPM[/bold cyan]")
    table.add_row("Accuracy", f"[bold {'green' if accuracy >= 95 else 'yellow' if accuracy >= 85 else 'red'}]{accuracy:.0f}%[/]")
    table.add_row("Time", f"{seconds:.1f} s")
    console.print(table)
    label = "custom" if custom is not None else mode
    new_best, data = save_result(label, wpm, accuracy, seconds)
    if new_best:
        console.print("[bold yellow]New personal best![/bold yellow]")
    recent = [h["wpm"] for h in data["history"][-12:]]
    console.print(f"[dim]Last {len(recent)} tests: {spark(recent)}  ({', '.join(map(str, recent[-5:]))} WPM)   tests: {data['tests']}[/dim]")


def read_custom(path):
    with open(fs.resolve(path) if fs else path, encoding="utf-8", errors="replace") as f:
        text = " ".join(f.read().split())
    if len(text) < 20:
        raise ValueError("that file has too little text (at least 20 characters)")
    return text[:600]


def default_mode():
    """The test the Choose prompt offers first: the 'default_mode' option from settings app games/typingtest (30 if none)."""
    try:
        from pyos import appsettings
        return str(appsettings.get("games/typingtest", "default_mode", "30"))
    except Exception:
        return "30"


def main(args):
    keys = Keys()
    try:
        if args and args[0] == "stats":
            stats()
            return
        if args and args[0] == "file" and len(args) > 1:
            run_test("file", keys, custom=read_custom(args[1]))
            return
        if args and args[0] in ("15", "30", "60", "words", "punct", "code", "quote"):
            run_test(args[0], keys)
            return
        console.print("[bold]Typing test[/bold]  15 / 30 / 60 (timed), words, punct (punctuation), code, quote, file <path>, stats, q")
        while True:
            choice = Prompt.ask("Choose", default=default_mode(), show_choices=False).strip().lower()
            if choice in ("q", "quit"):
                return
            if choice == "stats":
                stats()
            elif choice.startswith("file"):
                path = choice[4:].strip() or Prompt.ask("File")
                run_test("file", keys, custom=read_custom(path))
            elif choice in ("15", "30", "60", "words", "punct", "code", "quote"):
                run_test(choice, keys)
            else:
                console.print("[yellow]Pick one of: 15, 30, 60, words, punct, code, quote, file <path>, stats, q.[/yellow]")
            if keys.real_time:
                keys = Keys()
    finally:
        keys.close()


def execute(args=None):
    try:
        main(list(args or []))
    except (OSError, ValueError, PermissionError) as e:
        console.print(f"[red]{e}[/red]")
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
