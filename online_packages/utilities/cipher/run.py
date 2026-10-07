#!/usr/bin/env python3
"""Cipher: classic ciphers for puzzles, games and learning. They hide nothing from a computer - never use them for real secrets.

    cipher caesar 3 "Hello, World"          shift every letter by 3 (use a negative number to go back)
    cipher rot13 "Uryyb"                    the same as caesar 13 (and it undoes itself)
    cipher atbash "Hello"                   A<->Z, B<->Y ...
    cipher vigenere KEY "Attack at dawn"    encode with a keyword (add --decode to decode)
    cipher rail 3 "WEAREDISCOVERED"         rail fence with 3 rails (add --decode to decode)
    cipher crack "Khoor Zruog"              try all 25 caesar shifts and show the likeliest English
"""
import sys

from rich.console import Console
from rich.markup import escape

console = Console()
ALPHA = "abcdefghijklmnopqrstuvwxyz"
# how common each letter is in English (percent): what "crack" scores a guess against
FREQ = dict(zip(ALPHA, (8.2, 1.5, 2.8, 4.3, 12.7, 2.2, 2.0, 6.1, 7.0, 0.15, 0.77, 4.0, 2.4, 6.7, 7.5, 1.9, 0.095, 6.0, 6.3, 9.1, 2.8, 0.98, 2.4, 0.15, 2.0, 0.074)))


def shift_char(ch, n):
    if ch.lower() in ALPHA:
        base = "A" if ch.isupper() else "a"
        return chr((ord(ch) - ord(base) + n) % 26 + ord(base))
    return ch


def caesar(text, n):
    return "".join(shift_char(c, n) for c in text)


def atbash(text):
    return "".join((chr(ord("Z") - (ord(c) - ord("A"))) if c.isupper() else chr(ord("z") - (ord(c) - ord("a")))) if c.lower() in ALPHA else c for c in text)


def vigenere(text, key, decode=False):
    key = [ALPHA.index(k) for k in key.lower() if k in ALPHA]
    if not key:
        raise ValueError("the key needs at least one letter")
    out, i = [], 0
    for c in text:
        if c.lower() in ALPHA:
            out.append(shift_char(c, -key[i % len(key)] if decode else key[i % len(key)]))
            i += 1
        else:
            out.append(c)
    return "".join(out)


def _rails(length, rails):
    pattern, row, step = [], 0, 1
    for _ in range(length):
        pattern.append(row)
        if rails > 1:
            if row == 0:
                step = 1
            elif row == rails - 1:
                step = -1
            row += step
    return pattern


def rail_encode(text, rails):
    if rails < 2 or rails > max(2, len(text)):
        raise ValueError("use at least 2 rails, and no more than the length of the text")
    pattern = _rails(len(text), rails)
    return "".join(text[i] for r in range(rails) for i, p in enumerate(pattern) if p == r)


def rail_decode(text, rails):
    if rails < 2 or rails > max(2, len(text)):
        raise ValueError("use at least 2 rails, and no more than the length of the text")
    pattern = _rails(len(text), rails)
    order = [i for r in range(rails) for i, p in enumerate(pattern) if p == r]
    out = [""] * len(text)
    for position, char in zip(order, text):
        out[position] = char
    return "".join(out)


def english_score(text):
    """Higher is more like English (letter frequencies); used to rank the 25 caesar guesses."""
    letters = [c for c in text.lower() if c in ALPHA]
    if not letters:
        return 0.0
    return -sum(abs(letters.count(l) / len(letters) * 100 - FREQ[l]) for l in ALPHA)


def crack(text):
    """[(score, shift, text)] best first."""
    return sorted(((english_score(caesar(text, -n)), n, caesar(text, -n)) for n in range(1, 26)), reverse=True)


def main(argv):
    decode = "--decode" in argv
    args = [a for a in argv if a != "--decode"]
    if not args:
        console.print(__doc__)
        return 1
    kind, rest = args[0].lower(), args[1:]
    try:
        if kind == "caesar" and len(rest) >= 2:
            result = caesar(" ".join(rest[1:]), -int(rest[0]) if decode else int(rest[0]))
        elif kind == "rot13" and rest:
            result = caesar(" ".join(rest), 13)
        elif kind == "atbash" and rest:
            result = atbash(" ".join(rest))
        elif kind == "vigenere" and len(rest) >= 2:
            result = vigenere(" ".join(rest[1:]), rest[0], decode)
        elif kind in ("rail", "railfence") and len(rest) >= 2:
            result = (rail_decode if decode else rail_encode)(" ".join(rest[1:]), int(rest[0]))
        elif kind == "crack" and rest:
            for score, n, text in crack(" ".join(rest))[:5]:
                console.print(f"shift {n:2}  {escape(text)}")
            return 0
        else:
            console.print(__doc__)
            return 1
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    console.print(escape(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
