#!/usr/bin/env python3
"""PDF reader (pypdf).

    pdfread report.pdf                the first pages (1-3)
    pdfread report.pdf 5              page 5
    pdfread report.pdf 2-4,9          pages 2 to 4 and 9
    pdfread report.pdf --info         pages, title, author
    pdfread report.pdf --search tax   which pages contain a word
Scanned pages (pictures of text) have no text to read.
"""
import os
import re
import sys

from rich.console import Console
from rich.markup import escape

try:
    from pyos import fs
except ImportError:                                        # run on its own, outside PythonOS
    fs = None


def resolve(name):
    return fs.resolve(name) if fs else os.path.expanduser(name)

console = Console()
MAX_BYTES = 100 * 1024 * 1024


def parse_pages(spec, total):
    """The sorted page numbers (1-based) of '2-4,9' within `total` pages, or raises ValueError."""
    pages = set()
    for piece in spec.split(","):
        piece = piece.strip()
        match = re.fullmatch(r"(\d+)(?:-(\d+))?", piece)
        if not match:
            raise ValueError(f"'{piece}' is not a page or a range like 2-4")
        low, high = int(match.group(1)), int(match.group(2) or match.group(1))
        if low < 1 or high < low or high > total:
            raise ValueError(f"the file has {total} page(s); {piece} is outside that")
        pages.update(range(low, high + 1))
    return sorted(pages)


def page_text(reader, number):
    return (reader.pages[number - 1].extract_text() or "").strip()


def search(reader, word):
    """[(page, line)] for every line of text containing the word."""
    word = word.lower()
    found = []
    for number in range(1, len(reader.pages) + 1):
        for line in page_text(reader, number).splitlines():
            if word in line.lower():
                found.append((number, line.strip()))
    return found


def execute(args=None):
    args = list(args or [])
    try:
        import pypdf
    except ImportError:
        console.print("[bold red]pdfread needs the pypdf library. Install the app again: pkg install pdfread[/bold red]")
        return False
    info = "--info" in args
    query = None
    if "--search" in args:
        i = args.index("--search")
        query = " ".join(args[i + 1:])
        args = args[:i]
    args = [a for a in args if a != "--info"]
    if not args:
        console.print("[bold red]Usage:[/bold red] pdfread <file.pdf> [pages] [--info] [--search word]")
        return False
    try:
        path = resolve(args[0])
        if os.path.getsize(path) > MAX_BYTES:
            console.print("[bold red]pdfread: that file is bigger than 100 MB.[/bold red]")
            return False
        reader = pypdf.PdfReader(path)
        if reader.is_encrypted:
            console.print("[yellow]This PDF is password protected.[/yellow]")
            return False
        total = len(reader.pages)
        if info:
            meta = reader.metadata or {}
            console.print(f"{escape(os.path.basename(path))}: {total} page(s)")
            for label, key in (("Title", "/Title"), ("Author", "/Author"), ("Created", "/CreationDate"), ("Producer", "/Producer")):
                if meta.get(key):
                    console.print(f"  {label}: {escape(str(meta.get(key)))}")
            return True
        if query is not None:
            hits = search(reader, query) if query else []
            for number, line in hits[:40]:
                console.print(f"[bold]p.{number}[/bold]  {escape(line[:110])}")
            console.print(f"[dim]{len(hits)} line(s) mention '{escape(query)}'[/dim]" if hits else "[yellow]Not found (scanned pages have no text).[/yellow]")
            return bool(hits)
        pages = parse_pages(args[1], total) if len(args) > 1 else list(range(1, min(total, 3) + 1))
        for number in pages[:20]:
            text = page_text(reader, number)
            console.print(f"[bold blue]--- page {number} of {total} ---[/bold blue]")
            console.print(text or "[dim](no text on this page: it may be a scan)[/dim]", markup=not text, highlight=False)
        if len(pages) > 20:
            console.print(f"[dim]... {len(pages) - 20} more pages; ask for a smaller range.[/dim]")
        if len(args) == 1 and total > 3:
            console.print(f"[dim]{total} pages in all. pdfread {escape(args[0])} 4-6 shows more.[/dim]")
    except ValueError as e:
        console.print(f"[yellow]{escape(str(e))}[/yellow]")
        return False
    except OSError as e:
        console.print(f"[bold red]pdfread: {escape(args[0])}: {escape(fs.errtext(e) if fs else str(e))}[/bold red]")
        return False
    except Exception as e:                                 # noqa: BLE001 - not a PDF, or damaged
        console.print(f"[bold red]pdfread: cannot read {escape(args[0])} ({escape(str(e)[:80])})[/bold red]")
        return False
    return True


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
