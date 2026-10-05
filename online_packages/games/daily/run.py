#!/usr/bin/env python3
"""Daily puzzle: one puzzle a day, the same for everyone who plays on the same date (the date is the seed), so you can compare results.
Today's puzzle is a number-and-logic challenge: 'Four Numbers' - make the target with + - * / and each number used once. You can also
play any date with  daily 2026-12-25  or share a seed with  daily seed 12345. Your results and streak are saved."""
import ast
import datetime
import itertools
import random
import re
import sys
import zlib

from rich.console import Console

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()


def seed_for(day):
    """Everyone gets the same puzzle for the same date."""
    return zlib.crc32(day.isoformat().encode())


def make_puzzle(seed):
    """Four numbers (1-9, with a bigger one) and a target that can really be made from them. Returns (numbers, target, example)."""
    rng = random.Random(seed)
    while True:
        nums = [rng.randint(1, 9) for _ in range(3)] + [rng.choice([10, 12, 15, 20, 25])]
        rng.shuffle(nums)
        reachable = solutions(nums)
        targets = [t for t in reachable if 10 <= t <= 99 and reachable[t]]
        if targets:
            target = rng.choice(sorted(targets))
            return nums, target, reachable[target]


def solutions(nums):
    """{value: an expression} for every whole number reachable by combining all the numbers with + - * /."""
    results = {}

    def combine(items):
        if len(items) == 1:
            value, expr = items[0]
            if abs(value - round(value)) < 1e-9:
                results.setdefault(round(value), expr)
            return
        for i, j in itertools.permutations(range(len(items)), 2):
            (a, ea), (b, eb) = items[i], items[j]
            rest = [items[k] for k in range(len(items)) if k not in (i, j)]
            options = [(a + b, f"({ea}+{eb})"), (a * b, f"({ea}*{eb})")]
            if a >= b:
                options.append((a - b, f"({ea}-{eb})"))
            if b != 0 and a % b == 0:
                options.append((a / b, f"({ea}/{eb})"))
            for value, expr in options:
                combine(rest + [(value, expr)])

    combine([(n, str(n)) for n in nums])
    return results


def check_expression(text, nums, target):
    """Is `text` a valid answer? Returns (ok, message). Only digits, + - * / and brackets are allowed; each number is used exactly once."""
    text = text.replace(" ", "")
    if not text or any(ch not in "0123456789+-*/()" for ch in text):
        return False, "Use only the numbers, + - * / and brackets."
    used = sorted(int(n) for n in re.findall(r"\d+", text))
    if used != sorted(nums):
        return False, f"Use each of {sorted(nums)} exactly once."
    try:
        tree = ast.parse(text, mode="eval")
        value = _evaluate(tree.body)
    except (SyntaxError, ZeroDivisionError, ValueError):
        return False, "That is not a valid sum."
    if abs(value - target) < 1e-9:
        return True, "Correct!"
    return False, f"That makes {value:g}, not {target}."


def _evaluate(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.BinOp):
        a, b = _evaluate(node.left), _evaluate(node.right)
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        if isinstance(node.op, ast.Div):
            return a / b
    raise ValueError("unsupported")


def streak(history, today):
    """Consecutive days ending today (or yesterday) with a solved puzzle."""
    days = {datetime.date.fromisoformat(d) for d, r in history.items() if r.get("solved")}
    count, day = 0, today
    if day not in days:
        day -= datetime.timedelta(days=1)
    while day in days:
        count += 1
        day -= datetime.timedelta(days=1)
    return count


def play(seed, label, record_day=None):
    nums, target, example = make_puzzle(seed)
    console.print(f"[bold]Daily puzzle[/bold] ({label}, seed {seed})")
    console.print(f"Numbers: [bold cyan]{'  '.join(map(str, nums))}[/bold cyan]   Target: [bold yellow]{target}[/bold yellow]")
    console.print("Make the target using each number once with + - * / and brackets, like (3+5)*4. 'hint' shows the first operation, 'give up' shows an answer.")
    tries = 0
    while True:
        try:
            text = input("> ").strip()
        except EOFError:
            return None
        if text.lower() in ("q", "quit"):
            return None
        if text.lower() == "give up":
            console.print(f"One answer: {example} = {target}")
            return False if record_day is None else (record_day, False, tries)
        if text.lower() == "hint":
            m = re.search(r"\((\d+)[-+*/](\d+)\)", example)
            console.print(f"[dim]Try combining {m.group(1)} and {m.group(2)} first.[/dim]" if m else "[dim]No hint for this one.[/dim]")
            continue
        tries += 1
        ok, message = check_expression(text, nums, target)
        console.print(f"[{'green' if ok else 'yellow'}]{message}[/]")
        if ok:
            console.print(f"[bold green]Solved in {tries} {'try' if tries == 1 else 'tries'}![/bold green]")
            return True if record_day is None else (record_day, True, tries)


def main(args):
    today = datetime.date.today()
    seed, label, record_day = seed_for(today), "today", today
    if args and args[0] == "seed" and len(args) > 1 and args[1].isdigit():
        seed, label, record_day = int(args[1]), "shared seed", None
    elif args:
        try:
            day = datetime.date.fromisoformat(args[0])
            seed, label, record_day = seed_for(day), day.isoformat(), None
        except ValueError:
            console.print("[yellow]Use a date like 2026-12-25, or  seed 12345.[/yellow]")
            return
    result = play(seed, label, record_day)
    if isinstance(result, tuple) and appdata:
        day, solved, tries = result
        history = appdata.load("daily", {})
        previous = history.get(day.isoformat(), {})
        if not previous.get("solved"):
            history[day.isoformat()] = {"solved": solved, "tries": tries}
            appdata.save("daily", history)
        console.print(f"[dim]Streak: {streak(history, today)} day(s). Share your result: seed {seed}, {tries} tries.[/dim]")


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
