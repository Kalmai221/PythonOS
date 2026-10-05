#!/usr/bin/env python3
"""Markdown viewer: read your notes (and any .md or .txt file) with headings, lists, code and links nicely formatted. While reading: a table
of contents to jump to a section, search inside the document (with line numbers), and export to a plain text or HTML file.
Works with the Notes app: your notes in ~/notes show up here, and 'e' opens the built-in editor."""
import html
import os
import re

from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.prompt import Prompt
from rich.table import Table

from pyos import fs

console = Console()
EXTENSIONS = (".md", ".markdown", ".txt")
MAX_BYTES = 500_000


def home():
    name = fs.current_user()[0]
    return fs.home_dir(name) if name else fs.BASE_DIR


def documents(folder=None):
    """[(relative label, full path)] for notes first, then every markdown/text file in the home folder."""
    base = folder or home()
    found = []
    for root, dirs, files in os.walk(base):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            if name.lower().endswith(EXTENSIONS) and not name.startswith("."):
                full = os.path.join(root, name)
                found.append((os.path.relpath(full, base).replace(os.sep, "/"), full))
    found.sort(key=lambda item: (not item[0].startswith("notes/"), item[0].lower()))
    return found


def read(path):
    with open(path, "rb") as f:
        raw = f.read(MAX_BYTES)
    return raw.decode("utf-8", errors="replace")


def outline(text):
    """Headings of a document as [(level, title)]."""
    return [(len(m.group(1)), m.group(2).strip()) for m in re.finditer(r"^(#{1,4})\s+(.+)$", text, re.M)]


def headings(text):
    """[(level, title, line index)] for every heading outside code blocks."""
    out, in_code = [], False
    for i, line in enumerate(text.splitlines()):
        if line.strip().startswith("```"):
            in_code = not in_code
        m = None if in_code else re.match(r"^(#{1,6})\s+(.+?)\s*#*$", line)
        if m:
            out.append((len(m.group(1)), m.group(2).strip(), i))
    return out


def section(text, index):
    """The text of heading number `index` (0-based) up to the next heading of the same or a higher level."""
    heads = headings(text)
    lines = text.splitlines()
    level, _title, start = heads[index]
    end = len(lines)
    for lv, _t, i in heads[index + 1:]:
        if lv <= level:
            end = i
            break
    return "\n".join(lines[start:end])


def search_lines(text, term, context=1):
    """[(line number, line)] of lines containing term (case-insensitive), numbered from 1."""
    term = term.lower()
    return [(i, line) for i, line in enumerate(text.splitlines(), 1) if term in line.lower()]


def to_plain(text):
    """Markdown with the markup taken out: headings, emphasis, code fences and link syntax removed, link addresses kept."""
    out = []
    for line in text.splitlines():
        if line.strip().startswith("```"):
            continue
        line = re.sub(r"^#{1,6}\s+", "", line)
        line = re.sub(r"^\s*[-*+]\s+", "- ", line)
        line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", line)
        line = re.sub(r"(\*\*|__)(.+?)\1", r"\2", line)
        line = re.sub(r"(?<![\w*])[*_]([^*_]+)[*_](?![\w*])", r"\1", line)
        line = line.replace("`", "")
        out.append(line)
    return "\n".join(out) + "\n"


def to_html(markdown_text, title="Document"):
    """A small Markdown-to-HTML converter: headings, bold, italic, code, links, lists, quotes, rules and paragraphs."""
    def inline(t):
        t = html.escape(t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
        return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', t)

    out, para, in_list, in_code = [], [], None, False

    def flush():
        nonlocal para
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para = []

    def close_list():
        nonlocal in_list
        if in_list:
            out.append(f"</{in_list}>")
            in_list = None

    for line in markdown_text.splitlines():
        if line.strip().startswith("```"):
            flush()
            close_list()
            out.append("</pre>" if in_code else "<pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            flush()
            close_list()
            out.append(f"<h{len(m.group(1))}>{inline(m.group(2))}</h{len(m.group(1))}>")
        elif re.match(r"^\s*([-*+]|\d+\.)\s+", line):
            flush()
            kind = "ol" if re.match(r"^\s*\d+\.", line) else "ul"
            if in_list != kind:
                close_list()
                out.append(f"<{kind}>")
                in_list = kind
            out.append("<li>" + inline(re.sub(r"^\s*([-*+]|\d+\.)\s+", "", line)) + "</li>")
        elif line.startswith(">"):
            flush()
            close_list()
            out.append("<blockquote>" + inline(line.lstrip("> ")) + "</blockquote>")
        elif re.match(r"^\s*(---|\*\*\*)\s*$", line):
            flush()
            close_list()
            out.append("<hr>")
        elif not line.strip():
            flush()
            close_list()
        else:
            close_list()
            para.append(line.strip())
    flush()
    close_list()
    body = "\n".join(out)
    return (f"<!doctype html>\n<html><head><meta charset=\"utf-8\"><title>{html.escape(title)}</title>"
            "<style>body{font-family:sans-serif;max-width:46em;margin:2em auto;padding:0 1em;line-height:1.6}"
            "code,pre{background:#f2f2f2;padding:.1em .3em;border-radius:3px}pre{padding:1em}blockquote{border-left:4px solid #ccc;margin-left:0;"
            f"padding-left:1em;color:#555}}</style></head><body>\n{body}\n</body></html>\n")


def prepare(path):
    text = read(path)
    if path.lower().endswith(".txt") and not re.search(r"^(#{1,4}\s|[-*]\s|```)", text, re.M):
        text = text.replace("\n", "  \n")                 # plain notes: keep their line breaks
    return text


def render(text):
    with console.pager(styles=False) if len(text.splitlines()) > console.height - 4 else _nullcontext():
        console.print(Markdown(text, hyperlinks=True))


def export(label, text, kind, target=None):
    base = os.path.splitext(os.path.basename(label))[0]
    target = target or f"~/{base}.{'html' if kind == 'html' else 'txt'}"
    content = to_html(text, base) if kind == "html" else to_plain(text)
    with open(fs.resolve(target, write=True), "w", encoding="utf-8") as f:
        f.write(content)
    return target


def show(label, path):
    """Read one document: formatted, with a table of contents, search and export."""
    text = prepare(path)
    render(text)
    while True:
        heads = headings(text)
        hint = "(t)able of contents, " if heads else ""
        choice = Prompt.ask(f"{hint}(s)earch, (x) export, (b)ack", default="b").strip().lower()
        if choice in ("b", "q", ""):
            return
        if choice == "t" and heads:
            for i, (level, title, _line) in enumerate(heads, 1):
                console.print("  " * (level - 1) + f"[cyan]{i}[/cyan] {escape(title)}")
            pick = Prompt.ask("Section number to read (Enter to go back)", default="").strip()
            if pick.isdigit() and 1 <= int(pick) <= len(heads):
                render(section(text, int(pick) - 1))
        elif choice == "s":
            term = Prompt.ask("Find in this document").strip()
            hits = search_lines(text, term) if term else []
            for number, line in hits[:30]:
                console.print(f"[dim]{number:>4}[/dim]  " + escape(line.strip())[:110], highlight=False)
            console.print(f"[green]{len(hits)} line(s)[/green]" if hits else "[yellow]No match.[/yellow]")
        elif choice == "x":
            kind = Prompt.ask("Export as", choices=["txt", "html"], default="html")
            try:
                console.print(f"[green]Saved {escape(export(label, text, kind))}[/green]")
            except (OSError, PermissionError) as e:
                console.print(f"[red]{escape(fs.errtext(e))}[/red]")
        else:
            console.print("[yellow]Choose t, s, x or b.[/yellow]")


class _nullcontext:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def listing(items):
    table = Table(title="Your documents", header_style="bold blue")
    table.add_column("#", justify="right")
    table.add_column("File", style="cyan")
    table.add_column("Title", style="dim")
    for i, (label, path) in enumerate(items, 1):
        heads = outline(read(path)[:4000])
        first = heads[0][1] if heads else (read(path)[:60].strip().splitlines() or [""])[0]
        table.add_row(str(i), escape(label), escape(first[:50]))
    console.print(table)


def main(start=None):
    items = documents()
    if not items:
        console.print("[yellow]No notes or markdown files yet. Install the Notes app and write one, or create a .md file with 'edit'.[/yellow]")
        return
    if start:
        hits = [it for it in items if start.lower() in it[0].lower()]
        if hits:
            show(*hits[0])
            return
        console.print(f"[yellow]No document matches '{escape(start)}'.[/yellow]")
    while True:
        listing(items)
        choice = Prompt.ask("Number to read, (s)earch text, (e)dit, (q)uit", default="q").strip().lower()
        if choice == "q":
            return
        if choice == "s":
            term = Prompt.ask("Search for").strip().lower()
            hits = [(l, p) for l, p in items if term and term in read(p).lower()]
            console.print("Found in: " + (", ".join(escape(l) for l, _ in hits) if hits else "nothing"))
        elif choice == "e":
            num = Prompt.ask("Number to edit")
            if num.isdigit() and 1 <= int(num) <= len(items):
                try:
                    import importlib
                    importlib.import_module("commands.edit").execute([fs.display(items[int(num) - 1][1])])
                except ImportError:
                    console.print("[yellow]Use: edit <file>[/yellow]")
                items = documents()
        elif choice.isdigit() and 1 <= int(choice) <= len(items):
            show(*items[int(choice) - 1])
        else:
            console.print("[yellow]Pick a number from the list.[/yellow]")


def execute(args=None):
    try:
        main(" ".join(args) if args else None)
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    import sys
    execute(sys.argv[1:])
