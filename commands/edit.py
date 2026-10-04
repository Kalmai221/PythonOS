import os
from rich.console import Console
from rich.markup import escape
import pyos.fs as fs
from pyos import editor

console = Console()
config = {
    "name": "edit",
    "description": "Edit a text file (edit <file>; created when you save). Full screen on a real terminal, a line editor elsewhere.",
    "alias": ["nano", "file"],
}


def execute(args=None):
    if not args:
        console.print("[bold red]Usage:[/bold red] edit <file>")
        return False
    name = args[0]
    try:
        path = fs.resolve(name, write=True)
    except PermissionError as e:
        console.print(f"[bold red]edit: {escape(name)}: {e}[/bold red]")
        return False
    if os.path.isdir(path):
        console.print(f"[bold red]edit: {escape(name)}: is a directory[/bold red]")
        return False

    doc = editor.Document.open(path)
    try:
        if editor.can_use_fullscreen():
            editor.run_fullscreen(doc)
        else:
            editor.run_line_editor(doc, ask=lambda prompt: input(prompt), say=lambda text: console.print(text, markup=False, highlight=False))
    except OSError as e:
        console.print(f"[bold red]edit: {escape(name)}: {e}[/bold red]")
        return False
    return True
