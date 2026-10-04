# mkdir.py in commands directory
import os
from rich.console import Console
from rich.prompt import Prompt
import pyos.fs as fs

# Command metadata
config = {
    "name": "mkdir",
    "description": "Creates a new directory (mkdir <name>)."
}

console = Console()


def execute(args=None):
    names = args or [Prompt.ask("[bold cyan]Enter directory name to create:[/bold cyan]", default="")]
    names = [n for n in names if n]
    if not names:
        console.print("[bold red]No directory name provided. Aborting.[/bold red]")
        return
    for name in names:
        try:
            os.makedirs(fs.resolve(name, write=True), exist_ok=False)
            console.print(f"[bold green]Directory '{name}' created.[/bold green]")
        except FileExistsError:
            console.print(f"[bold yellow]'{name}' already exists.[/bold yellow]")
        except Exception as e:
            console.print(f"[bold red]Error creating '{name}': {e}[/bold red]")
