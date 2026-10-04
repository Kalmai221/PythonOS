#!/usr/bin/env python3
import random
from rich.console import Console
from rich.prompt import Prompt

console = Console()

WORDS = [
    "python", "kernel", "terminal", "compiler", "variable", "function", "network", "keyboard",
    "database", "algorithm", "function", "package", "process", "memory", "shell", "program",
    "internet", "browser", "software", "hardware", "library", "monitor", "backup", "folder",
]

STAGES = [
    "  +---+\n      |\n      |\n      |\n     ===",
    "  +---+\n  O   |\n      |\n      |\n     ===",
    "  +---+\n  O   |\n  |   |\n      |\n     ===",
    "  +---+\n  O   |\n /|   |\n      |\n     ===",
    "  +---+\n  O   |\n /|\\  |\n      |\n     ===",
    "  +---+\n  O   |\n /|\\  |\n /    |\n     ===",
    "  +---+\n  O   |\n /|\\  |\n / \\  |\n     ===",
]


def play():
    word = random.choice(WORDS)
    guessed, wrong = set(), 0
    while True:
        console.clear()
        console.print("[bold]Hangman[/bold]\n")
        console.print(STAGES[wrong])
        shown = " ".join(c if c in guessed else "_" for c in word)
        console.print(f"\n{shown}\n")
        console.print(f"Wrong guesses: [red]{', '.join(sorted(guessed - set(word))) or '-'}[/red]  ({6 - wrong} left)")
        if all(c in guessed for c in word):
            console.print("\n[bold green]You got it![/bold green]")
            return
        if wrong >= 6:
            console.print(f"\n[bold red]Out of guesses. The word was '{word}'.[/bold red]")
            return
        guess = Prompt.ask("\nGuess a letter (or the whole word, q to quit)").strip().lower()
        if guess == "q":
            return
        if len(guess) > 1:
            if guess == word:
                guessed.update(word)
            else:
                wrong += 1
        elif guess.isalpha() and guess not in guessed:
            guessed.add(guess)
            if guess not in word:
                wrong += 1


def main():
    while True:
        play()
        if Prompt.ask("\nPlay again?", choices=["y", "n"], default="y") == "n":
            break


if __name__ == "__main__":
    main()


def execute():
    main()
