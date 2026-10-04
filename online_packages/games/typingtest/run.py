#!/usr/bin/env python3
"""Typing test: type the words shown as fast and accurately as you can. Reports words per minute and accuracy and
keeps your best scores. Plain Python, nothing to install."""
import difflib
import random
import time

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

try:
    from pyos import appdata
except ImportError:
    appdata = None

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
    "How vexingly quick daft zebras jump!",
    "Sphinx of black quartz, judge my vow.",
    "A journey of a thousand miles begins with a single step.",
    "Programs must be written for people to read, and only incidentally for machines to execute.",
    "Simple is better than complex. Complex is better than complicated.",
    "Readability counts. Special cases are not special enough to break the rules.",
]


def score(target, typed, seconds):
    """(wpm, accuracy %, correct characters). A 'word' is five characters, the usual convention."""
    matcher = difflib.SequenceMatcher(None, target, typed, autojunk=False)
    correct = sum(block.size for block in matcher.get_matching_blocks())
    accuracy = 100 * correct / max(len(target), len(typed), 1)
    wpm = (correct / 5) / max(seconds / 60, 1 / 600)
    return wpm, accuracy, correct


def marked(target, typed):
    out = Text()
    matcher = difflib.SequenceMatcher(None, target, typed, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            out.append(target[i1:i2], style="green")
        elif tag in ("replace", "delete"):
            out.append(target[i1:i2], style="bold red underline")
    return out


def make_text(mode):
    if mode == "sentence":
        return random.choice(SENTENCES)
    count = {"words": 25, "short": 12, "long": 50}[mode]
    return " ".join(random.choice(COMMON) for _ in range(count))


def load():
    return appdata.load("typingtest", {"best_wpm": 0, "tests": 0, "history": []}) if appdata else {"best_wpm": 0, "tests": 0, "history": []}


def run_test(mode):
    target = make_text(mode)
    console.print(Panel(target, title="Type this", border_style="blue"))
    input("Press Enter, then start typing and press Enter when you finish... ")
    console.print("[bold green]Go![/bold green]")
    start = time.time()
    typed = input("> ")
    seconds = time.time() - start
    wpm, accuracy, correct = score(target, typed, seconds)
    console.print(Panel(marked(target, typed), title="What you typed vs the text (red = wrong or missed)", border_style="blue"))
    table = Table(show_header=False, box=None)
    table.add_row("Speed", f"[bold cyan]{wpm:.0f} WPM[/bold cyan]")
    table.add_row("Accuracy", f"[bold {'green' if accuracy >= 95 else 'yellow' if accuracy >= 85 else 'red'}]{accuracy:.0f}%[/]")
    table.add_row("Time", f"{seconds:.1f} s")
    console.print(table)
    data = load()
    data["tests"] += 1
    if accuracy >= 90 and wpm > data["best_wpm"]:
        data["best_wpm"] = round(wpm)
        console.print("[bold yellow]New personal best![/bold yellow]")
    data["history"] = (data.get("history", []) + [{"wpm": round(wpm), "acc": round(accuracy)}])[-20:]
    if appdata:
        appdata.save("typingtest", data)
    recent = [h["wpm"] for h in data["history"][-5:]]
    console.print(f"[dim]Best: {data['best_wpm']} WPM (90%+ accuracy)   last {len(recent)}: {', '.join(map(str, recent))}   tests: {data['tests']}[/dim]")


def main():
    console.print("[bold]Typing test[/bold]")
    while True:
        mode = Prompt.ask("Text: short (12 words), words (25), long (50), sentence, or q to quit",
                          choices=["short", "words", "long", "sentence", "q"], default="words", show_choices=False)
        if mode == "q":
            return
        run_test(mode)


def execute():
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute()
