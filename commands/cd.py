# In commands/cd.py
import os
from rich.console import Console

console = Console()

# Metadata dictionary for the command
config = {
    "name": "cd",
    "description": "Change the current directory."
}

# Global reference for current directory
current_directory = os.path.abspath("files")  # Starts in 'files'
base_directory = current_directory  # Base directory shouldn't be exposed

# Path to store the current directory
current_directory_file = "current_directory.txt"

def get_relative_path():
    """Returns the shell path, hiding 'files' and showing a clean prompt."""
    relative_path = os.path.relpath(current_directory, base_directory)
    return f"/{relative_path}" if relative_path != "." else ""

def load_current_directory():
    """Load the current directory from a file."""
    global current_directory
    if os.path.exists(current_directory_file):
        with open(current_directory_file, 'r') as f:
            current_directory = f.read().strip()

def save_current_directory():
    """Save the current directory to a file."""
    with open(current_directory_file, 'w') as f:
        f.write(current_directory)

def execute(args=None):
    """Handles 'cd' command logic and updates current_directory."""
    global current_directory  # Ensure we're updating the global variable

    # Load the current directory from the file
    load_current_directory()

    if args is None or args.strip() == "":
        console.print(f"Current directory: [bold yellow]{get_relative_path()}[/bold yellow]")
        return

    new_path = os.path.abspath(os.path.join(current_directory, args.strip()))

    if new_path.startswith(base_directory) and os.path.isdir(new_path):
        current_directory = new_path
        save_current_directory()  # Save the new directory
        console.print(f"Changed directory to: [bold green]{get_relative_path()}[/bold green]")
    else:
        console.print("[bold red]Error:[/bold red] Invalid directory or access denied.")
