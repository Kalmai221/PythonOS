#!/usr/bin/env python3
"""Readability: how long and how hard a text is to read.

    readability essay.txt          words, sentences, reading time, grade level, the words you use most
    some-command | readability     the same for piped text
"""
import collections
import os
import re
import sys

from rich.console import Console
from rich.table import Table

console = Console()
STOP = set("the a an and or but of to in on at for with by from is are was were be been it its this that these those as he she they we you i not no "
           "so if then than there their them his her our your my me what which who when where how do does did have has had will would can could "
           "should about into over just also more most some such only".split())


def syllables(word):
    """A rough count (good enough for a reading level): groups of vowels, minus a silent final e."""
    word = re.sub(r"[^a-z]", "", word.lower())
    if not word:
        return 0
    count = len(re.findall(r"[aeiouy]+", word))
    if word.endswith("e") and not word.endswith(("le", "ee")) and count > 1:
        count -= 1
    return max(count, 1)


def analyse(text):
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    sentences = [s for s in re.split(r"[.!?]+(?:\s+|$)", text) if re.search(r"[A-Za-z]", s)]
    n_words, n_sent = len(words), max(len(sentences), 1)
    n_syll = sum(syllables(w) for w in words)
    result = {"characters": len(text), "words": n_words, "sentences": len(sentences) if words else 0,
              "paragraphs": len([p for p in re.split(r"\n\s*\n", text) if p.strip()]),
              "minutes": n_words / 230 if n_words else 0.0, "speaking_minutes": n_words / 140 if n_words else 0.0}
    if n_words:
        per_sentence, per_word = n_words / n_sent, n_syll / n_words
        result["flesch"] = 206.835 - 1.015 * per_sentence - 84.6 * per_word                 # higher = easier
        result["grade"] = 0.39 * per_sentence + 11.8 * per_word - 15.59                       # US school grade
        result["avg_sentence"] = per_sentence
    counts = collections.Counter(w.lower().strip("'-") for w in words if w.lower() not in STOP and len(w) > 2)
    result["top"] = counts.most_common(8)
    return result


def describe_flesch(score):
    for limit, label in ((90, "very easy"), (80, "easy"), (70, "fairly easy"), (60, "plain English"), (50, "fairly hard"), (30, "hard")):
        if score >= limit:
            return label
    return "very hard"


def main(argv):
    if argv:
        path = argv[0]
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as e:
            console.print(f"[red]Cannot read {path}: {e.strerror or e}[/red]")
            return 1
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        console.print(__doc__)
        return 1
    stats = analyse(text)
    if not stats["words"]:
        console.print("There are no words to measure.")
        return 1
    table = Table(show_header=False, box=None)
    for label, value in (("Words", stats["words"]), ("Sentences", stats["sentences"]), ("Paragraphs", stats["paragraphs"]),
                         ("Average sentence", f"{stats['avg_sentence']:.1f} words"),
                         ("Reading time", f"{max(stats['minutes'], 0.1):.1f} min (speaking {stats['speaking_minutes']:.1f} min)"),
                         ("Reading ease", f"{stats['flesch']:.0f} - {describe_flesch(stats['flesch'])}"),
                         ("School grade", f"{max(stats['grade'], 0):.1f}")):
        table.add_row(f"[bold]{label}[/bold]", str(value))
    console.print(table)
    if stats["top"]:
        console.print("[bold]Most used:[/bold] " + ", ".join(f"{w} ({n})" for w, n in stats["top"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
