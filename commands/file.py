import os
import subprocess
from rich.console import Console
from rich.prompt import Prompt
import pyos.fs as fs

console = Console()

config = {
    "name": "file",
    "description": "Open a file in a text editor, creating it if needed (edit <file>).",
    "alias": ["edit", "nano"]
}


def execute(args=None):
    name = args[0] if args else Prompt.ask("[bold yellow]File to edit[/bold yellow]").strip()
    if not name:
        return
    try:
        path = fs.resolve(name, write=True)
    except PermissionError as e:
        console.print(f"[bold red]{name}: {e}[/bold red]")
        return
    if os.path.isdir(path):
        console.print(f"[bold red]{name}: is a directory[/bold red]")
        return

    editor = "notepad" if os.name == "nt" else "nano"
    try:
        subprocess.run([editor, path])
    except FileNotFoundError:
        console.print(f"[bold red]'{editor}' is not installed or not available on this system.[/bold red]")
