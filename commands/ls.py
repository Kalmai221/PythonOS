import os
from rich.console import Console
from rich.text import Text

console = Console()

# Metadata dictionary for commands
config = {
    "name": "ls",
    "description": "List files and folders in the current directory"
}

def execute(args=None):
    """Lists files and directories based on the directory specified in current_directory.txt."""
    try:
        # Read the current directory from current_directory.txt
        current_directory_file = "current_directory.txt"

        if not os.path.exists(current_directory_file):
            console.print(f"[bold red]Error:[/bold red] {current_directory_file} not found.")
            return

        with open(current_directory_file, "r") as file:
            current_directory = file.read().strip()

        # Check if the directory exists
        if not os.path.isdir(current_directory):
            console.print(f"[bold red]Error:[/bold red] {current_directory} is not a valid directory.")
            return

        # List files in the directory
        files = os.listdir(current_directory)

        if not files:
            console.print("[bold yellow]Directory is empty.[/bold yellow]")
            return

        # Format and display the output
        formatted_output = Text()
        for item in files:
            item_path = os.path.join(current_directory, item)
            if os.path.isdir(item_path):
                formatted_output.append(f"{item}/  ", style="bold blue")  # Directories in blue
            else:
                formatted_output.append(f"{item}  ", style="white")  # Files in white

        console.print(formatted_output)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
