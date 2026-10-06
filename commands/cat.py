import os

from rich.console import Console

import pyos.fs as fs
import pyos.stdio as stdio
from pyos import filetypes

console = Console()
config = {"name": "cat", "description": "Print the contents of a file (cat [--plain] <file>); code, JSON and Markdown files are coloured on a terminal."}
COLOUR_LIMIT = 256 * 1024
LEXERS = {".py": "python", ".json": "json", ".md": "markdown", ".markdown": "markdown", ".js": "javascript", ".html": "html", ".htm": "html", ".css": "css",
          ".sh": "bash", ".yml": "yaml", ".yaml": "yaml", ".toml": "toml", ".ini": "ini", ".xml": "xml", ".c": "c", ".h": "c", ".cpp": "cpp", ".java": "java",
          ".rs": "rust", ".go": "go", ".sql": "sql", ".ps1": "powershell", ".bat": "batch", ".cs": "csharp", ".kt": "kotlin", ".cfg": "ini"}


def lexer_for(name, text):
    """The Pygments lexer name for a file, or None (unknown type or too big to colour)."""
    if len(text) > COLOUR_LIMIT:
        return None
    return LEXERS.get(os.path.splitext(name)[1].lower())


def plain(text):
    # print exactly what is in the file (no extra blank line after a final newline)
    console.print(text, markup=False, highlight=False, end="" if text.endswith("\n") or not text else "\n")


def show(name, text):
    """Print a file's text: coloured when this is a real terminal and the type is known, else exactly as it is."""
    lexer = lexer_for(name, text) if console.is_terminal else None
    if lexer:
        try:
            from rich.syntax import Syntax
            console.print(Syntax(text, lexer, theme="ansi_dark", background_color="default", word_wrap=True))
            return
        except Exception:                                  # noqa: BLE001 - colouring must never stop a file from showing
            pass
    plain(text)


def execute(args=None):
    args = list(args or [])
    no_colour = "--plain" in args
    force = "--force" in args
    args = [a for a in args if a not in ("--plain", "--force")]
    if not args:
        if stdio.read_stdin() is not None:
            console.print(stdio.read_stdin(), markup=False, highlight=False, end="")
            return True
        console.print("[bold red]Usage:[/bold red] cat [--plain] <file>")
        return False
    ok = True
    for name in args:
        try:
            path = fs.resolve(name)
            with open(path, "rb") as probe:
                head = probe.read(4096)
            if not force and head and not filetypes.is_text(head):
                console.print(f"[yellow]cat: {name} is not text ({filetypes.describe(head, name)}). Use cat --force to print it anyway, or file {name}.[/yellow]")
                ok = False
                continue
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            if no_colour:
                plain(text)
            else:
                show(name, text)
        except Exception as e:
            console.print(f"[bold red]cat: {name}: {fs.errtext(e)}[/bold red]")
            ok = False
    return ok
