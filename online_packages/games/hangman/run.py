#!/usr/bin/env python3
import random
from rich.console import Console
from rich.prompt import Prompt

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()

CATEGORIES = {
    "computers": ["python", "kernel", "terminal", "compiler", "variable", "function", "network", "keyboard", "database",
                  "algorithm", "package", "process", "memory", "shell", "program", "internet", "browser", "software",
                  "hardware", "library", "monitor", "backup", "folder", "router", "encryption", "firewall"],
    "animals": ["elephant", "giraffe", "penguin", "dolphin", "kangaroo", "octopus", "crocodile", "butterfly", "squirrel",
                "hedgehog", "flamingo", "leopard", "tortoise", "peacock", "wolverine", "chameleon"],
    "countries": ["australia", "brazil", "canada", "denmark", "ethiopia", "finland", "germany", "hungary", "iceland",
                  "jamaica", "kenya", "lithuania", "mexico", "norway", "portugal", "vietnam", "zimbabwe"],
    "food": ["pancake", "spaghetti", "avocado", "broccoli", "croissant", "dumpling", "lasagne", "mushroom", "pineapple",
             "strawberry", "sandwich", "chocolate", "pretzel", "burrito", "cinnamon"],
}

STAGES = [
    "  +---+\n      |\n      |\n      |\n     ===",
    "  +---+\n  O   |\n      |\n      |\n     ===",
    "  +---+\n  O   |\n  |   |\n      |\n     ===",
    "  +---+\n  O   |\n /|   |\n      |\n     ===",
    "  +---+\n  O   |\n /|\\  |\n      |\n     ===",
    "  +---+\n  O   |\n /|\\  |\n /    |\n     ===",
    "  +---+\n  O   |\n /|\\  |\n / \\  |\n     ===",
]


def play(category):
    """True if the word was found, False if not, None if the player quit."""
    word = random.choice(CATEGORIES[category])
    guessed, wrong = set(), 0
    while True:
        console.print(f"\n[bold]Hangman[/bold] [dim]({category})[/dim]\n")
        console.print(STAGES[wrong])
        shown = " ".join(c if c in guessed else "_" for c in word)
        console.print(f"\n{shown}\n")
        console.print(f"Wrong guesses: [red]{', '.join(sorted(guessed - set(word))) or '-'}[/red]  ({6 - wrong} left)")
        if all(c in guessed for c in word):
            console.print("\n[bold green]You got it![/bold green]")
            return True
        if wrong >= 6:
            console.print(f"\n[bold red]Out of guesses. The word was '{word}'.[/bold red]")
            return False
        guess = Prompt.ask("\nGuess a letter (or the whole word, q to quit)").strip().lower()
        if guess == "q":
            return None
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
    category = Prompt.ask("Category", choices=list(CATEGORIES), default="computers")
    stats = appdata.load("hangman", {"won": 0, "lost": 0}) if appdata else None
    while True:
        result = play(category)
        if result is None:
            break
        if stats is not None:
            stats["won" if result else "lost"] += 1
            appdata.save("hangman", stats)
            console.print(f"[dim]Won {stats['won']}, lost {stats['lost']}[/dim]")
        if Prompt.ask("\nPlay again?", choices=["y", "n"], default="y") == "n":
            break


if __name__ == "__main__":
    main()


def execute():
    main()
