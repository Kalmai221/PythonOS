#!/usr/bin/env python3
"""xkcd: read a comic from the terminal (xkcd.com, no account or key).

    xkcd                 today's comic
    xkcd random          a surprise
    xkcd 353             comic number 353
    xkcd 353 --save      also save the picture into your files (xkcd-353.png)
The picture itself cannot be drawn here, so you get the title, the date and the text that shows when you hover over it, which is often the joke.
"""
import random
import sys
import textwrap

import requests
from rich.console import Console
from rich.markup import escape

console = Console()
HEADERS = {"User-Agent": "PythonOS-xkcd/1.0 (https://github.com/Kalmai221/PythonOS)"}


def fetch(number=None):
    url = "https://xkcd.com/info.0.json" if number is None else f"https://xkcd.com/{number}/info.0.json"
    response = requests.get(url, timeout=10, headers=HEADERS)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def describe(comic):
    """The lines shown for a comic's JSON."""
    date = "-".join(str(comic.get(k, "?")).zfill(2 if k != "year" else 4) for k in ("year", "month", "day"))
    lines = [f"xkcd {comic.get('num', '?')}: {comic.get('safe_title') or comic.get('title', '?')}", f"Published {date}"]
    alt = " ".join((comic.get("alt") or "").split())
    if alt:
        lines += ["", "Hover text:"] + textwrap.wrap(alt, 72)
    transcript = (comic.get("transcript") or "").strip()
    if transcript:
        lines += ["", "Transcript:"] + [l for l in transcript.splitlines() if l.strip()][:12]
    return lines


def parse(argv):
    """(number, random?, save?) from the arguments. Raises ValueError."""
    argv, save, number, pick = list(argv), False, None, False
    if "--save" in argv:
        argv.remove("--save")
        save = True
    for word in argv:
        if word.lower() == "random":
            pick = True
        elif word.isdigit() and int(word) > 0:
            number = int(word)
        else:
            raise ValueError(f"I do not understand '{word}'.")
    return number, pick, save


def main(argv):
    try:
        number, pick, save = parse(argv)
    except ValueError as e:
        console.print(__doc__)
        console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    try:
        if pick:
            latest = fetch()["num"]
            number = random.randint(1, latest)
            if number == 404:                                     # the joke: comic 404 does not exist
                number = 405
        comic = fetch(number)
        if comic is None:
            console.print(f"[red]There is no xkcd number {number}.[/red]")
            return 1
        title, *rest = describe(comic)
        console.print(f"[bold]{escape(title)}[/bold]")
        for line in rest:
            console.print(escape(line))
        console.print(f"\n[dim]xkcd.com/{comic.get('num')}[/dim]")
        if save and comic.get("img"):
            picture = requests.get(comic["img"], timeout=15, headers=HEADERS)
            picture.raise_for_status()
            name = f"xkcd-{comic.get('num')}.png"
            with open(name, "wb") as f:
                f.write(picture.content)
            console.print(f"Saved {name}")
    except (requests.RequestException, ValueError, KeyError) as e:
        console.print(f"[red]Could not reach xkcd ({escape(type(e).__name__)}). Check the internet connection.[/red]")
        return 1
    except OSError as e:
        console.print(f"[red]Could not save the picture: {escape(str(e))}[/red]")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
