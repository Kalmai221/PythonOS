#!/usr/bin/env python3
"""Book search: Open Library (openlibrary.org, no account or key).

    books dune                       books with that in the title
    books --author tolkien           by an author
    books --isbn 9780441172719       one book by its ISBN
    books "foundation" -n 20         more results (up to 30)
"""
import sys

import requests
from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()
SEARCH = "https://openlibrary.org/search.json"
FIELDS = "title,author_name,first_publish_year,number_of_pages_median,edition_count,key,subject"
HEADERS = {"User-Agent": "PythonOS-books/1.0 (https://github.com/Kalmai221/PythonOS)"}


def build_query(argv):
    """(params for the search, how many) from the arguments. Raises ValueError when there is nothing to look for."""
    argv, count = list(argv), 10
    if "-n" in argv:
        i = argv.index("-n")
        try:
            count = max(1, min(int(argv[i + 1]), 30))
        except (IndexError, ValueError):
            raise ValueError("-n needs a number") from None
        del argv[i:i + 2]
    params = {"fields": FIELDS, "limit": count}
    for flag, key in (("--author", "author"), ("--isbn", "isbn")):
        if flag in argv:
            i = argv.index(flag)
            value = " ".join(argv[i + 1:]).strip()
            if not value:
                raise ValueError(f"{flag} needs a value")
            params[key] = value
            return params, count
    if not argv:
        raise ValueError("What should I look for?")
    params["title"] = " ".join(argv)
    return params, count


def parse(data):
    """[{'title', 'authors', 'year', 'pages', 'editions', 'subjects'}] from the search answer."""
    books = []
    for doc in data.get("docs", []):
        if not doc.get("title"):
            continue
        books.append({"title": doc["title"], "authors": ", ".join((doc.get("author_name") or [])[:3]) or "unknown",
                      "year": doc.get("first_publish_year"), "pages": doc.get("number_of_pages_median"),
                      "editions": doc.get("edition_count") or 0, "subjects": (doc.get("subject") or [])[:4]})
    return books


def main(argv):
    try:
        params, _count = build_query(argv)
    except ValueError as e:
        console.print(__doc__)
        console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    try:
        response = requests.get(SEARCH, params=params, timeout=15, headers=HEADERS)
        response.raise_for_status()
        books = parse(response.json())
    except (requests.RequestException, ValueError) as e:
        console.print(f"[red]Could not search Open Library ({escape(type(e).__name__)}). Check the internet connection.[/red]")
        return 1
    if not books:
        console.print("Nothing found. Try fewer or different words.")
        return 0
    table = Table()
    for column in ("Title", "Author", "First published", "Pages", "Editions"):
        table.add_column(column)
    for b in books:
        table.add_row(escape(b["title"]), escape(b["authors"]), str(b["year"] or "?"), str(b["pages"] or "?"), str(b["editions"]))
    console.print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
