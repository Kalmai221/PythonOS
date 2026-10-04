# In commands/cd.py
import os
from rich.console import Console
import pyos.fs as fs

console = Console()

# Metadata dictionary for the command
config = {
    "name": "cd",
    "description": "Change the current directory."
}


def execute(args=None):
    """Handles 'cd' command logic and updates the saved current directory."""
    target = " ".join(args).strip() if isinstance(args, list) else (args or "").strip()

    if not target:
        target = "~"

    try:
        new_path = fs.resolve(target)
    except PermissionError:
        console.print(f"[bold red]cd: {target}: Permission denied[/bold red]")
        return

    if os.path.isdir(new_path):
        fs.save_current_dir(new_path)
    else:
        console.print(f"[bold red]cd: {target}: No such directory[/bold red]")
