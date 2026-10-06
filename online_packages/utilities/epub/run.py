#!/usr/bin/env python3
"""Book reader for EPUB files (ebooklib).

    epub book.epub                list the chapters
    epub book.epub 3              read chapter 3
    epub book.epub --info         title, author, language
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
MAX_BYTES = 200 * 1024 * 1024


def chapters(book):
    """[(title, html bytes)] for the documents of the book in reading order."""
    import ebooklib
    out = []
    spine = [item for item, _linear in book.spine if isinstance(item, str)]
    by_id = {item.get_id(): item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)}
    ordered = [by_id[i] for i in spine if i in by_id] or list(by_id.values())
    for number, item in enumerate(ordered, 1):
        title = ""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(item.get_content(), "html.parser")
            heading = soup.find(["h1", "h2", "h3", "title"])
            title = heading.get_text(" ", strip=True) if heading else ""
        except Exception:                                  # noqa: BLE001
            pass
        out.append((title or f"Part {number}", item.get_content()))
    return out


def to_text(html):
    """Readable text from a chapter's HTML."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    for tag in soup.find_all(["br"]):
        tag.replace_with("\n")
    for tag in soup.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "tr"]):
        tag.insert_after("\n\n")                           # a paragraph break after each block, without splitting words inside a paragraph
    text = soup.get_text("")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def meta(book, field):
    values = book.get_metadata("DC", field)
    return values[0][0] if values else ""


def execute(args=None):
    args = list(args or [])
    try:
        from ebooklib import epub
        import bs4  # noqa: F401
    except ImportError:
        console.print("[bold red]epub needs the ebooklib and beautifulsoup4 libraries. Install the app again: pkg install epub[/bold red]")
        return False
    info = "--info" in args
    args = [a for a in args if a != "--info"]
    if not 1 <= len(args) <= 2:
        console.print("[bold red]Usage:[/bold red] epub <book.epub> [chapter] [--info]")
        return False
    try:
        path = resolve(args[0])
        if os.path.getsize(path) > MAX_BYTES:
            console.print("[bold red]epub: that file is bigger than 200 MB.[/bold red]")
            return False
        book = epub.read_epub(path, {"ignore_ncx": True})
        parts = chapters(book)
    except OSError as e:
        console.print(f"[bold red]epub: {escape(args[0])}: {escape(fs.errtext(e) if fs else str(e))}[/bold red]")
        return False
    except Exception as e:                                 # noqa: BLE001 - not an EPUB, or damaged
        console.print(f"[bold red]epub: cannot read {escape(args[0])} ({escape(str(e)[:80])})[/bold red]")
        return False
    if info:
        for label, field in (("Title", "title"), ("Author", "creator"), ("Language", "language"), ("Publisher", "publisher")):
            if meta(book, field):
                console.print(f"{label}: {escape(meta(book, field))}")
        console.print(f"Chapters: {len(parts)}")
        return True
    if len(args) == 1:
        console.print(f"[bold]{escape(meta(book, 'title') or os.path.basename(path))}[/bold]  [dim]{escape(meta(book, 'creator'))}[/dim]")
        for number, (title, _html) in enumerate(parts, 1):
            console.print(f"{number:>4}. {escape(title[:80])}")
        console.print(f"[dim]Read one with: epub {escape(args[0])} <number>[/dim]")
        return True
    if not args[1].isdigit() or not 1 <= int(args[1]) <= len(parts):
        console.print(f"[yellow]Chapter numbers go from 1 to {len(parts)}.[/yellow]")
        return False
    title, html = parts[int(args[1]) - 1]
    console.print(f"[bold blue]{escape(title)}[/bold blue]\n")
    console.print(to_text(html), markup=False, highlight=False)
    return True


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
