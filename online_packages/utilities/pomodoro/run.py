#!/usr/bin/env python3
"""Pomodoro: work in focused blocks with short breaks.

    pomodoro                    4 rounds of 25 minutes of work and 5 of break
    pomodoro 50 10 3            50 minutes of work, 10 of break, 3 rounds
Ctrl+C stops. A bell rings when a block ends (if your terminal plays it).
"""
import sys
import time

from rich.console import Console
from rich.live import Live
from rich.panel import Panel

console = Console()


def clock(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def parse(args):
    """(work, break, rounds) in minutes and rounds from the command line, with the usual 25/5/4 for what is left out. None if invalid."""
    values = [25, 5, 4]
    for index, text in enumerate(args[:3]):
        if not text.isdigit() or not 1 <= int(text) <= (12 if index == 2 else 240):
            return None
        values[index] = int(text)
    return tuple(values)


def block(label, minutes, style, rounds_text):
    total = minutes * 60
    start = time.monotonic()
    with Live(console=console, refresh_per_second=4) as live:
        while True:
            left = total - (time.monotonic() - start)
            if left <= 0:
                break
            done = int(30 * (1 - left / total))
            live.update(Panel(f"[bold {style}]{label}[/bold {style}]  {rounds_text}\n\n[bold]{clock(left + 0.99)}[/bold]\n[{style}]{'#' * done}[/{style}][dim]{'-' * (30 - done)}[/dim]",
                              expand=False, border_style=style))
            time.sleep(0.25)
    console.print("\a", end="")


def execute(args=None):
    plan = parse(list(args or []))
    if plan is None:
        console.print("pomodoro [work minutes [break minutes [rounds]]]   for example: pomodoro 50 10 3")
        return False
    work, rest, rounds = plan
    try:
        for number in range(1, rounds + 1):
            block("Focus", work, "red", f"round {number} of {rounds}")
            console.print(f"[green]Round {number} done.[/green]")
            if number < rounds:
                block("Break", rest, "green", f"after round {number}")
        console.print(f"[bold green]All {rounds} rounds done: {rounds * work} minutes of focus. Well done.[/bold green]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped.[/yellow]")
    return True


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
