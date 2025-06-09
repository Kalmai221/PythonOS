# mkdir.py in commands directory

import os
from rich.console import Console
from rich.prompt import Prompt

# Command metadata
config = {
    "name": "mkdir",
    "description": "Creates a new directory with the specified name."
}

console = Console()

def execute():
    dirname = Prompt.ask("[bold cyan]Enter directory name to create:[/bold cyan]", default="")
    if not dirname:
        console.print("[bold red]No directory name provided. Aborting.[/bold red]")
        return

    try:
        os.makedirs(dirname, exist_ok=False)
        console.print(f"[bold green]Directory '{dirname}' created successfully.[/bold green]")
    except FileExistsError:
        console.print(f"[bold yellow]Directory '{dirname}' already exists.[/bold yellow]")
    except Exception as e:
        console.print(f"[bold red]Error creating directory '{dirname}': {e}[/bold red]")
