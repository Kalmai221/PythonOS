#!/usr/bin/env python3
"""Text tools: count words, characters and lines; change case; sort, reverse and remove duplicate lines; trim spaces; find and replace;
make a URL-friendly slug; wrap text to a width; number lines; extract email addresses and links. Works on text you type or a file.
Usage: texttools <tool> <text or @file>  (for example: texttools upper hello  |  texttools count @~/notes/a.txt)  |  texttools (menu).
Tools: count upper lower title swapcase sort unique reverse trim slug wrap number emails links replace"""
import re
import sys
import textwrap

from rich.console import Console
from rich.markup import escape
from rich.prompt import IntPrompt, Prompt
from rich.table import Table

try:
    from pyos import fs
except ImportError:
    fs = None

console = Console()


def read_source(text):
    """Text typed as is, or the contents of a file when it starts with @."""
    if text.startswith("@") and len(text) > 1:
        with open(fs.resolve(text[1:]) if fs else text[1:], encoding="utf-8", errors="replace") as f:
            return f.read()
    return text


def count(text):
    words = re.findall(r"\S+", text)
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    return {"characters": len(text), "characters (no spaces)": len(re.sub(r"\s", "", text)), "words": len(words),
            "lines": len(text.splitlines()) if text else 0, "sentences": len(sentences),
            "paragraphs": len([p for p in re.split(r"\n\s*\n", text) if p.strip()]),
            "reading time": f"{max(1, round(len(words) / 220))} min" if words else "0 min"}


def slug(text):
    text = re.sub(r"[^\w\s-]", "", text.lower().encode("ascii", "ignore").decode())
    return re.sub(r"[-\s]+", "-", text).strip("-")


def sort_lines(text, reverse=False, numeric=False):
    lines = text.splitlines()
    if numeric:
        def key(line):
            m = re.search(r"-?\d+(?:\.\d+)?", line)
            return (float(m.group(0)) if m else float("inf"), line)
        return "\n".join(sorted(lines, key=key, reverse=reverse))
    return "\n".join(sorted(lines, key=str.lower, reverse=reverse))


def unique_lines(text):
    seen, out = set(), []
    for line in text.splitlines():
        if line not in seen:
            seen.add(line)
            out.append(line)
    return "\n".join(out)


def number_lines(text):
    return "\n".join(f"{i:>4}  {line}" for i, line in enumerate(text.splitlines(), 1))


def emails(text):
    return "\n".join(dict.fromkeys(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)))


def links(text):
    return "\n".join(dict.fromkeys(re.findall(r"https?://[^\s<>\"')]+", text)))


def wrap(text, width=70):
    return "\n\n".join(textwrap.fill(p, width) for p in re.split(r"\n\s*\n", text))


def replace(text, old, new, ignore_case=False):
    return re.sub(re.escape(old), new.replace("\\", "\\\\"), text, flags=re.IGNORECASE if ignore_case else 0)


TOOLS = {
    "upper": str.upper, "lower": str.lower, "title": str.title, "swapcase": str.swapcase,
    "sort": sort_lines, "unique": unique_lines, "reverse": lambda t: "\n".join(reversed(t.splitlines())),
    "trim": lambda t: "\n".join(line.strip() for line in t.splitlines()), "slug": slug, "number": number_lines,
    "emails": emails, "links": links, "wrap": wrap,
}


def run(tool, text, extra=()):
    if tool == "count":
        table = Table(show_header=False, box=None)
        for name, value in count(text).items():
            table.add_row(name, str(value))
        console.print(table)
        return None
    if tool == "replace":
        if len(extra) < 2:
            raise ValueError("replace needs the text to find and what to put instead")
        return replace(text, extra[0], extra[1])
    if tool == "wrap" and extra and extra[0].isdigit():
        return wrap(text, int(extra[0]))
    if tool not in TOOLS:
        raise ValueError(f"unknown tool '{tool}' (count, replace, {', '.join(TOOLS)})")
    return TOOLS[tool](text)


def show(result):
    if result is not None:
        console.print(result, markup=False, highlight=False)


def main(args):
    if len(args) >= 2:
        tool = args[0].lower()
        extra = []
        if tool == "replace" and len(args) >= 4:
            extra, body = args[1:3], " ".join(args[3:])
        elif tool == "wrap" and len(args) >= 3 and args[1].isdigit():
            extra, body = [args[1]], " ".join(args[2:])
        else:
            body = " ".join(args[1:])
        show(run(tool, read_source(body), extra))
        return
    if args:
        console.print("texttools <tool> <text or @file>   tools: count replace " + " ".join(TOOLS))
        return
    names = ["count", "replace", *TOOLS]
    while True:
        console.print("Tools: " + ", ".join(names))
        tool = Prompt.ask("Tool (q to quit)").strip().lower()
        if tool in ("q", "quit"):
            return
        if tool not in names:
            console.print("[yellow]Pick one of the tools above.[/yellow]")
            continue
        console.print("[dim]Type the text (or @file); finish with a line containing just a dot (.)[/dim]")
        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip() == ".":
                break
            lines.append(line)
        try:
            body = read_source(lines[0]) if len(lines) == 1 and lines[0].startswith("@") else "\n".join(lines)
            extra = []
            if tool == "replace":
                extra = [Prompt.ask("Find"), Prompt.ask("Replace with", default="")]
            elif tool == "wrap":
                extra = [str(IntPrompt.ask("Width", default=70))]
            show(run(tool, body, extra))
        except (OSError, ValueError, PermissionError) as e:
            console.print(f"[red]{escape(fs.errtext(e) if fs and isinstance(e, OSError) else str(e))}[/red]")


def execute(args=None):
    try:
        main(list(args or []))
    except (OSError, ValueError, PermissionError) as e:
        console.print(f"[red]{escape(fs.errtext(e) if fs and isinstance(e, OSError) else str(e))}[/red]")
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
