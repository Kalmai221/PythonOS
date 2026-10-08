#!/usr/bin/env python3
"""Hacker News: the front page from the terminal (hacker-news.firebaseio.com, no account or key).

    hn                    the top 15 stories
    hn new                the newest
    hn best -n 30         the best of the past days, 30 of them
    hn ask                Ask HN      (also: show, jobs)
Each line has the points, the comments and the site the story is from. Open a story's discussion with its number: hn 12 (the 12th line).
"""
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests
from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()
BASE = "https://hacker-news.firebaseio.com/v0/"
HEADERS = {"User-Agent": "PythonOS-hn/1.0 (https://github.com/Kalmai221/PythonOS)"}
LISTS = {"top": "topstories", "new": "newstories", "best": "beststories", "ask": "askstories", "show": "showstories", "jobs": "jobstories"}


def get(path):
    response = requests.get(BASE + path, timeout=10, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def site(url):
    """'example.com' for a story's address, '' when it has none (Ask HN)."""
    host = urllib.parse.urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def parse_args(argv):
    """(list name, how many, item number or None). Raises ValueError."""
    argv, count, kind, number = list(argv), 15, "top", None
    if "-n" in argv:
        i = argv.index("-n")
        try:
            count = max(1, min(int(argv[i + 1]), 50))
        except (IndexError, ValueError):
            raise ValueError("-n needs a number") from None
        del argv[i:i + 2]
    for word in argv:
        if word.lower() in LISTS:
            kind = word.lower()
        elif word.isdigit():
            number = int(word)
        else:
            raise ValueError(f"I do not understand '{word}'.")
    return kind, count, number


def story(item):
    """The facts shown about one item of the service ({} for a missing or removed one)."""
    if not item or item.get("deleted") or item.get("dead"):
        return {}
    return {"id": item.get("id"), "title": item.get("title") or "(no title)", "score": item.get("score", 0), "comments": item.get("descendants", 0),
            "by": item.get("by", "?"), "site": site(item.get("url")), "text": item.get("text") or ""}


def fetch_stories(kind, count):
    ids = get(LISTS[kind] + ".json")[:count]
    with ThreadPoolExecutor(max_workers=8) as pool:
        items = list(pool.map(lambda i: story(get(f"item/{i}.json")), ids))
    return [s for s in items if s]


def main(argv):
    try:
        kind, count, number = parse_args(argv)
    except ValueError as e:
        console.print(__doc__)
        console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    try:
        stories = fetch_stories(kind, max(count, number or 0))
        if number is not None:
            if not 1 <= number <= len(stories):
                console.print(f"[red]There is no story number {number} in that list.[/red]")
                return 1
            s = stories[number - 1]
            console.print(f"[bold]{escape(s['title'])}[/bold]\n{s['score']} points by {escape(s['by'])}, {s['comments']} comments" + (f", from {escape(s['site'])}" if s["site"] else ""))
            console.print(f"[dim]Discussion: news.ycombinator.com item {s['id']}[/dim]")
            return 0
    except (requests.RequestException, ValueError) as e:
        console.print(f"[red]Could not reach Hacker News ({escape(type(e).__name__)}). Check the internet connection.[/red]")
        return 1
    table = Table(title=f"Hacker News: {kind}")
    for column, justify in (("#", "right"), ("Story", "left"), ("Site", "left"), ("Points", "right"), ("Comments", "right")):
        table.add_column(column, justify=justify)
    for number_, s in enumerate(stories[:count], 1):
        table.add_row(str(number_), escape(s["title"]), escape(s["site"]), str(s["score"]), str(s["comments"]))
    console.print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
