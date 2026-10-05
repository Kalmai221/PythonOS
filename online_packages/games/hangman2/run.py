#!/usr/bin/env python3
"""Hangman for two players: one person types a secret word (or phrase) - the screen is cleared so the other cannot see it - and the
other guesses letters. Swap roles each round; the scores add up."""
import sys

from rich.console import Console
from rich.prompt import Prompt

console = Console()
STAGES = [
    "  +---+\n      |\n      |\n      |\n     ===",
    "  +---+\n  O   |\n      |\n      |\n     ===",
    "  +---+\n  O   |\n  |   |\n      |\n     ===",
    "  +---+\n  O   |\n /|   |\n      |\n     ===",
    "  +---+\n  O   |\n /|\\  |\n      |\n     ===",
    "  +---+\n  O   |\n /|\\  |\n /    |\n     ===",
    "  +---+\n  O   |\n /|\\  |\n / \\  |\n     ===",
]
MAX_WRONG = 6


def valid_secret(text):
    """A secret is letters, spaces and hyphens, 2 to 40 characters, with at least two letters."""
    text = text.strip().lower()
    letters = [c for c in text if c.isalpha()]
    return len(text) <= 40 and len(letters) >= 2 and all(c.isalpha() or c in " -'" for c in text)


def masked(secret, guessed):
    return " ".join(c if (c in guessed or not c.isalpha()) else "_" for c in secret)


def solved(secret, guessed):
    return all(c in guessed for c in secret if c.isalpha())


def hide_screen():
    from pyos import stdio
    try:
        stdio.clear_screen()
    except Exception:
        console.print("\n" * 40)


def guess_round(secret, guesser):
    guessed, wrong = set(), 0
    while True:
        console.print(f"\n[bold]{guesser}[/bold], the word so far:")
        console.print(STAGES[wrong])
        console.print(f"\n{masked(secret, guessed)}\n")
        console.print(f"Wrong: [red]{', '.join(sorted(c for c in guessed if c not in secret)) or '-'}[/red]  ({MAX_WRONG - wrong} left)")
        if solved(secret, guessed):
            console.print(f"[bold green]{guesser} found it![/bold green]")
            return True
        if wrong >= MAX_WRONG:
            console.print(f"[bold red]Out of guesses. It was '{secret}'.[/bold red]")
            return False
        try:
            text = Prompt.ask("Guess a letter (or the whole answer)").strip().lower()
        except EOFError:
            return None
        if len(text) == 1 and text.isalpha():
            if text in guessed:
                console.print("[yellow]You already tried that.[/yellow]")
                continue
            guessed.add(text)
            if text not in secret:
                wrong += 1
        elif len(text) > 1:
            if text == secret:
                guessed.update(c for c in secret if c.isalpha())
            else:
                wrong += 1


def main():
    p1 = Prompt.ask("Player 1 name", default="Player 1").strip() or "Player 1"
    p2 = Prompt.ask("Player 2 name", default="Player 2").strip() or "Player 2"
    score = {p1: 0, p2: 0}
    setter, guesser = p1, p2
    while True:
        while True:
            console.print(f"\n[bold]{setter}[/bold], type a secret word or phrase (it will be hidden). {guesser}, look away!")
            secret = Prompt.ask("Secret", password=True).strip().lower()
            if valid_secret(secret):
                break
            console.print("[yellow]Use letters (and spaces or hyphens), at least two letters.[/yellow]")
        hide_screen()
        result = guess_round(secret, guesser)
        if result is None:
            return
        score[guesser if result else setter] += 1
        console.print(f"[dim]{p1} {score[p1]} - {score[p2]} {p2}[/dim]")
        if Prompt.ask("Another round (roles swap)?", choices=["y", "n"], default="y") == "n":
            winner = max(score, key=score.get)
            console.print("[bold]It is a tie![/bold]" if score[p1] == score[p2] else f"[bold green]{winner} wins the match![/bold green]")
            return
        setter, guesser = guesser, setter


def execute(args=None):
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
