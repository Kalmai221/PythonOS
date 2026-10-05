#!/usr/bin/env python3
"""Blackjack against the dealer. Get closer to 21 than the dealer without going over. Aces count 1 or 11, face cards 10. Blackjack
(an ace and a ten-card on the deal) pays 3 to 2. The dealer stands on 17. You start with 100 chips (play money; it carries over).
Commands: h (hit), s (stand), d (double down), q (cash out)."""
import random
import sys

from rich.console import Console
from rich.text import Text

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["S", "H", "D", "C"]


def new_deck(rng=None, decks=4):
    deck = [(r, s) for _ in range(decks) for r in RANKS for s in SUITS]
    (rng or random).shuffle(deck)
    return deck


def value(hand):
    """Best total of a hand: aces are 11 unless that would go over 21."""
    total = sum(11 if r == "A" else 10 if r in "JQK" or r == "10" else int(r) for r, _ in hand)
    aces = sum(r == "A" for r, _ in hand)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def is_blackjack(hand):
    return len(hand) == 2 and value(hand) == 21


def show(hand, hide_second=False):
    out = Text()
    for i, (r, s) in enumerate(hand):
        if hide_second and i == 1:
            out.append("[??] ", style="dim")
        else:
            out.append(f"[{r}{s}] ", style="bold red" if s in "HD" else "bold white")
    return out


def settle(player, dealer, bet):
    """Chips won (positive) or lost (negative) for a finished round, plus a message."""
    p, d = value(player), value(dealer)
    if p > 21:
        return -bet, "Bust - you lose."
    if is_blackjack(player) and not is_blackjack(dealer):
        return bet * 3 // 2, "Blackjack! Pays 3 to 2."
    if d > 21:
        return bet, "The dealer busts - you win."
    if is_blackjack(dealer) and not is_blackjack(player):
        return -bet, "The dealer has blackjack."
    if p > d:
        return bet, "You win."
    if p < d:
        return -bet, "The dealer wins."
    return 0, "Push (a tie): your bet is returned."


def round_(chips, deck):
    """Play one hand. Returns the new chip total, or None if the player cashes out."""
    while True:
        try:
            text = input(f"Chips {chips}. Bet (1-{chips}, Enter = {min(10, chips)}, q = cash out)> ").strip().lower()
        except EOFError:
            return None
        if text in ("q", "quit"):
            return None
        bet = min(10, chips) if not text else int(text) if text.isdigit() else 0
        if 1 <= bet <= chips:
            break
        console.print("[yellow]Bet a whole number of chips you have.[/yellow]")
    if len(deck) < 20:
        deck[:] = new_deck()
    player, dealer = [deck.pop(), deck.pop()], [deck.pop(), deck.pop()]
    doubled = False
    while True:
        console.print(Text("Dealer: ") + show(dealer, hide_second=True))
        console.print(Text(f"You ({value(player)}): ") + show(player))
        if value(player) >= 21 or is_blackjack(dealer):
            break
        options = "(h)it, (s)tand" + (", (d)ouble" if len(player) == 2 and chips >= bet * 2 else "")
        try:
            choice = input(f"{options}> ").strip().lower()[:1]
        except EOFError:
            return None
        if choice == "h":
            player.append(deck.pop())
        elif choice == "s":
            break
        elif choice == "d" and len(player) == 2 and chips >= bet * 2:
            bet *= 2
            doubled = True
            player.append(deck.pop())
            console.print(Text(f"Doubled to {bet}. You ({value(player)}): ") + show(player))
            break
    if value(player) <= 21 and not is_blackjack(player):
        while value(dealer) < 17:
            dealer.append(deck.pop())
    console.print(Text(f"Dealer ({value(dealer)}): ") + show(dealer))
    change, message = settle(player, dealer, bet)
    console.print(f"[bold {'green' if change > 0 else 'red' if change < 0 else 'yellow'}]{message}[/] ({change:+d} chips)")
    return chips + change


def main():
    chips = appdata.load("blackjack", {}).get("chips", 100) if appdata else 100
    if chips <= 0:
        chips = 100
        console.print("[dim]Fresh stack of 100 chips.[/dim]")
    deck = new_deck()
    console.print("[bold]Blackjack[/bold]  dealer stands on 17, blackjack pays 3:2, play money only.")
    while chips > 0:
        result = round_(chips, deck)
        if result is None:
            break
        chips = result
        if appdata:
            appdata.save("blackjack", {"chips": chips})
    if chips <= 0:
        console.print("[bold red]You are out of chips. Start again next time with 100.[/bold red]")
        if appdata:
            appdata.save("blackjack", {"chips": 100})
    else:
        console.print(f"You cash out with {chips} chips.")


def execute(args=None):
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
