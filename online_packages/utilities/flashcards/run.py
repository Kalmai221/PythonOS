#!/usr/bin/env python3
"""Flashcards: make decks of question and answer cards and study them with spaced repetition (the Leitner boxes).

A card you know moves up a box and comes back later (1, 2, 4, 8, 16 days); a card you miss goes back to the first box.
    flashcards                   the menu
    flashcards study <deck>      study the cards that are due in a deck
    flashcards list              the decks and how many cards are due
"""
import datetime
import json
import os
import random
import sys

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

console = Console()
INTERVALS = {1: 0, 2: 1, 3: 2, 4: 4, 5: 8, 6: 16}     # days until a card in this box is asked again
TOP_BOX = 6


def data_file():
    """Per-user storage inside the PyOS home directory (falls back to files/)."""
    try:
        with open("current_user.json") as f:
            user = json.load(f)["username"]
    except Exception:
        user = None
    folder = os.path.join("files", "home", user) if user else "files"
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, ".flashcards.json")


def load():
    try:
        with open(data_file()) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(decks):
    with open(data_file(), "w") as f:
        json.dump(decks, f, indent=2)


def today():
    return datetime.date.today()


def is_due(card, on=None):
    return card.get("due", "") <= (on or today()).isoformat()


def due_cards(cards, on=None):
    return [c for c in cards if is_due(c, on)]


def answer(card, knew, on=None):
    """Move a card after it was answered: up a box and later when known, back to the first box (due today) when missed."""
    on = on or today()
    box = min(TOP_BOX, card.get("box", 1) + 1) if knew else 1
    card["box"] = box
    card["due"] = (on + datetime.timedelta(days=INTERVALS[box])).isoformat()
    return card


def new_card(question, reply):
    return {"q": question.strip(), "a": reply.strip(), "box": 1, "due": today().isoformat()}


def show_decks(decks):
    if not decks:
        console.print("[yellow]No decks yet. Make one with 'n'.[/yellow]")
        return
    table = Table(header_style="bold blue")
    for column in ("Deck", "Cards", "Due now", "Learned"):
        table.add_column(column, justify="right" if column != "Deck" else "left")
    for name, cards in sorted(decks.items()):
        table.add_row(name, str(len(cards)), str(len(due_cards(cards))), str(sum(1 for c in cards if c.get("box", 1) >= TOP_BOX)))
    console.print(table)


def study(decks, name):
    cards = decks.get(name)
    if cards is None:
        console.print(f"[red]No deck called {name}.[/red]")
        return
    queue = due_cards(cards)
    if not queue:
        console.print("[green]Nothing is due in this deck. Come back later.[/green]")
        return
    random.shuffle(queue)
    right = 0
    for number, card in enumerate(queue, 1):
        console.print(f"\n[dim]{number}/{len(queue)}[/dim]  [bold]{card['q']}[/bold]")
        Prompt.ask("[dim]Press Enter to see the answer[/dim]", default="", show_default=False)
        console.print(f"[cyan]{card['a']}[/cyan]")
        knew = Prompt.ask("Did you know it? (y)es (n)o (q)uit", choices=["y", "n", "q"], default="y")
        if knew == "q":
            break
        answer(card, knew == "y")
        right += knew == "y"
        save(decks)
    console.print(f"\n[bold]Done:[/bold] {right} of {number} known.")


def menu():
    decks = load()
    while True:
        console.print("\n[bold]Flashcards[/bold]")
        show_decks(decks)
        action = Prompt.ask("(s)tudy  (n)ew deck  (a)dd cards  (c)ards  (d)elete deck  (q)uit", choices=["s", "n", "a", "c", "d", "q"], default="q")
        if action == "q":
            break
        if action == "n":
            name = Prompt.ask("Name of the new deck").strip()
            if name and name not in decks:
                decks[name] = []
        elif decks:
            name = Prompt.ask("Which deck", choices=sorted(decks))
            if action == "s":
                study(decks, name)
            elif action == "a":
                console.print("[dim]An empty question ends.[/dim]")
                while True:
                    question = Prompt.ask("Question").strip()
                    if not question:
                        break
                    reply = Prompt.ask("Answer").strip()
                    if reply:
                        decks[name].append(new_card(question, reply))
            elif action == "c":
                for number, card in enumerate(decks[name], 1):
                    console.print(f"{number:>3}. {card['q']}  [dim]->[/dim]  {card['a']}  [dim](box {card.get('box', 1)})[/dim]")
            elif action == "d" and Prompt.ask(f"Delete the deck {name}? (yes/no)", choices=["yes", "no"], default="no") == "yes":
                del decks[name]
        else:
            console.print("[yellow]Make a deck first.[/yellow]")
        save(decks)


def execute(args=None):
    try:
        args = list(args or [])
        if args[:1] == ["list"]:
            show_decks(load())
        elif args[:1] == ["study"] and len(args) > 1:
            decks = load()
            study(decks, " ".join(args[1:]))
        else:
            menu()
    except (KeyboardInterrupt, EOFError):
        console.print()
    return True


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
