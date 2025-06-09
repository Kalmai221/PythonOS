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
    # Always create inside /files, no chdir needed
    files_dir = "/files"  # or your absolute path here
    new_dir_path = os.path.join(files_dir, dirname)

    try:
        os.makedirs(new_dir_path, exist_ok=False)
        console.print(f"[bold green]Directory '{dirname}' created successfully inside /files.[/bold green]")
    except FileExistsError:
        console.print(f"[bold yellow]Directory '{dirname}' already exists inside /files.[/bold yellow]")
    except Exception as e:
        console.print(f"[bold red]Error creating directory '{dirname}': {e}[/bold red]")
