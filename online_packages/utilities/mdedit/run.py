#!/usr/bin/env python3
"""Markdown editor with a live preview. Type lines to add them; after every change the formatted page is drawn next to (or under) the
source, so you see headings, lists, bold, code and links as you write. Commands start with a colon:
  :open <file>  :save [file]  :new  :list  :del N  :ins N <text>  :set N <text>  :undo  :h1/:h2/:h3 <text>  :bullet <text>  :todo <text>
  :code (start/end a code block)  :quote <text>  :html <file> (export a web page)  :width N  :quit
Anything not starting with a colon is added as a new line of text."""
import html
import re
import sys

from rich.columns import Columns
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

try:
    from pyos import fs
except ImportError:
    fs = None

console = Console()


class Doc:
    def __init__(self, lines=None, path=None):
        self.lines = list(lines or [])
        self.path = path
        self.history = []
        self.dirty = False
        self.in_code = False

    def snapshot(self):
        self.history.append(list(self.lines))
        del self.history[:-50]
        self.dirty = True

    def undo(self):
        if not self.history:
            return False
        self.lines = self.history.pop()
        return True

    def add(self, text):
        self.snapshot()
        self.lines.append(text)

    def insert(self, n, text):
        if not 1 <= n <= len(self.lines) + 1:
            return False
        self.snapshot()
        self.lines.insert(n - 1, text)
        return True

    def set(self, n, text):
        if not 1 <= n <= len(self.lines):
            return False
        self.snapshot()
        self.lines[n - 1] = text
        return True

    def delete(self, n):
        if not 1 <= n <= len(self.lines):
            return False
        self.snapshot()
        del self.lines[n - 1]
        return True

    def text(self):
        return "\n".join(self.lines)


def resolve(path, write=False):
    return fs.resolve(path, write=write) if fs else path


def load(path):
    with open(resolve(path), encoding="utf-8") as f:
        return Doc(f.read().splitlines(), path)


def save(doc, path=None):
    path = path or doc.path
    if not path:
        raise ValueError("give a file name:  :save notes.md")
    with open(resolve(path, write=True), "w", encoding="utf-8") as f:
        f.write(doc.text() + "\n")
    doc.path, doc.dirty = path, False
    return path


def to_html(markdown_text, title="Document"):
    """A small Markdown-to-HTML converter: headings, bold, italic, code, links, lists, quotes, rules and paragraphs."""
    def inline(s):
        s = html.escape(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
        return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)

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


def draw(doc, width=None):
    """The source (numbered) and the preview, side by side on a wide screen and one above the other on a narrow one."""
    width = width or console.width
    source = Text()
    for i, line in enumerate(doc.lines, 1):
        source.append(f"{i:>3} ", style="dim")
        source.append(line + "\n")
    if not doc.lines:
        source.append("(empty - type a line to begin)", style="dim")
    preview = Markdown(doc.text() or "*nothing yet*")
    title = f"Source{' *' if doc.dirty else ''}  {doc.path or '(unsaved)'}"
    if width >= 100:
        half = (width - 4) // 2
        console.print(Columns([Panel(source, title=title, width=half, border_style="blue"),
                               Panel(preview, title="Preview", width=half, border_style="green")]))
    else:
        console.print(Panel(source, title=title, border_style="blue"))
        console.print(Panel(preview, title="Preview", border_style="green"))


HELP = __doc__.split("Commands start with a colon:")[1].split("Anything not starting")[0]


def command(doc, line):
    """Handle a ':' command. Returns 'quit' to leave."""
    parts = line[1:].split(None, 1)
    cmd, rest = (parts[0].lower(), parts[1] if len(parts) > 1 else "") if parts else ("", "")
    if cmd in ("q", "quit", "exit"):
        return "quit"
    if cmd in ("h", "help"):
        console.print(HELP, markup=False)
    elif cmd == "new":
        doc.lines, doc.path, doc.history, doc.dirty = [], None, [], False
    elif cmd == "open" and rest:
        loaded = load(rest)
        doc.lines, doc.path, doc.history, doc.dirty = loaded.lines, rest, [], False
    elif cmd == "save":
        console.print(f"[green]Saved {escape(save(doc, rest or None))}[/green]")
        return None
    elif cmd == "list":
        pass
    elif cmd == "undo":
        if not doc.undo():
            console.print("[yellow]Nothing to undo.[/yellow]")
    elif cmd == "del" and rest.isdigit():
        if not doc.delete(int(rest)):
            console.print("[yellow]No such line.[/yellow]")
    elif cmd in ("ins", "set") and rest:
        n, _, text = rest.partition(" ")
        if not n.isdigit() or not (doc.insert if cmd == "ins" else doc.set)(int(n), text):
            console.print("[yellow]Use  :ins N text  or  :set N text  with a valid line number.[/yellow]")
    elif cmd in ("h1", "h2", "h3"):
        doc.add("#" * int(cmd[1]) + " " + rest)
    elif cmd == "bullet":
        doc.add("- " + rest)
    elif cmd == "todo":
        doc.add("- [ ] " + rest)
    elif cmd == "quote":
        doc.add("> " + rest)
    elif cmd == "code":
        doc.add("```")
    elif cmd == "html" and rest:
        with open(resolve(rest, write=True), "w", encoding="utf-8") as f:
            f.write(to_html(doc.text(), doc.path or "Document"))
        console.print(f"[green]Exported {escape(rest)}[/green]")
        return None
    else:
        console.print("[yellow]Unknown command. :help lists them.[/yellow]")
        return None
    return None


def main(args):
    doc = load(args[0]) if args else Doc()
    console.print("[bold]Markdown editor[/bold]  type text to add a line; commands start with ':'  (:help, :save, :quit)")
    draw(doc)
    while True:
        try:
            line = input("md> ")
        except EOFError:
            return
        try:
            if line.startswith(":"):
                if command(doc, line) == "quit":
                    if doc.dirty:
                        answer = input("You have unsaved changes. Quit anyway? [y/N] ").strip().lower()
                        if answer != "y":
                            continue
                    return
            elif line.strip() or doc.lines:
                doc.add(line)
        except (OSError, ValueError, PermissionError) as e:
            console.print(f"[red]{escape(fs.errtext(e) if fs and isinstance(e, OSError) else str(e))}[/red]")
        draw(doc)


def execute(args=None):
    try:
        main(list(args or []))
    except (OSError, PermissionError) as e:
        console.print(f"[red]{escape(fs.errtext(e) if fs else str(e))}[/red]")
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
