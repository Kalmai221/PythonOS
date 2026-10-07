#!/usr/bin/env python3
"""Morse: turn text into Morse code and back, see the table, and practise.

    morse encode "SOS help"        -> ... --- ...  .... . .-.. .--.     (a / between words)
    morse decode "... --- ..."     -> SOS
    morse table                    every letter and digit
    morse quiz                     guess the letter for a code (q to stop)
"""
import random
import sys

from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt

console = Console()
CODE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..", "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...",
    "8": "---..", "9": "----.", ".": ".-.-.-", ",": "--..--", "?": "..--..", "'": ".----.", "!": "-.-.--", "/": "-..-.", ":": "---...", "-": "-....-",
}
REVERSE = {v: k for k, v in CODE.items()}


def encode(text):
    """Letters separated by a space, words by ' / '. Characters Morse has no code for are left out."""
    words = []
    for word in text.upper().split():
        letters = [CODE[c] for c in word if c in CODE]
        if letters:
            words.append(" ".join(letters))
    return " / ".join(words)


def decode(code):
    """The reverse. '/' (or three or more spaces) separates words; an unknown code becomes '?'."""
    code = code.strip().replace("  /  ", " / ")
    words = []
    for chunk in code.replace("   ", " / ").split("/"):
        words.append("".join(REVERSE.get(sym, "?") for sym in chunk.split()))
    return " ".join(w for w in words if w)


def main(argv):
    if not argv:
        console.print(__doc__)
        return 1
    command, rest = argv[0].lower(), " ".join(argv[1:])
    if command == "encode" and rest:
        console.print(escape(encode(rest)))
        return 0
    if command == "decode" and rest:
        console.print(escape(decode(rest)))
        return 0
    if command == "table":
        items = list(CODE.items())
        for i in range(0, len(items), 4):
            console.print("   ".join(f"{k}  {v:<7}" for k, v in items[i:i + 4]))
        return 0
    if command == "quiz":
        right = total = 0
        keys = [k for k in CODE if k.isalnum()]
        while True:
            letter = random.choice(keys)
            answer = Prompt.ask(f"{CODE[letter]}   which character?").strip().upper()
            if answer in ("Q", "QUIT"):
                break
            total += 1
            if answer == letter:
                right += 1
                console.print("[green]yes[/green]")
            else:
                console.print(f"[red]no, it is {letter}[/red]")
        console.print(f"{right} of {total} right.")
        return 0
    console.print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
