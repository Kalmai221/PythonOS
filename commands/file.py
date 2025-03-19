import os
import subprocess
from rich.console import Console
from rich.prompt import Prompt

console = Console()

config = {
    "name": "file",
    "description": "Create, edit, or delete files."
}

FILES_DIRECTORY = "files"  # Directory to store files (make sure it exists)

def create_file():
    """Create a new file."""
    file_name = Prompt.ask("[bold yellow]Enter the name of the file to create[/bold yellow]").strip()
    file_path = os.path.join(FILES_DIRECTORY, file_name)

    # Check if the file already exists
    if os.path.exists(file_path):
        console.print(f"[bold red]Error:[/bold red] File '{file_name}' already exists.")
        return

    # Create the new file
    with open(file_path, 'w') as file:
        content = Prompt.ask("[bold yellow]Enter content for the file[/bold yellow]")
        file.write(content)
        console.print(f"[bold green]File '{file_name}' created successfully![/bold green]")

def edit_file():
    """Edit an existing file using nano."""
    file_name = Prompt.ask("[bold yellow]Enter the name of the file to edit[/bold yellow]").strip()
    file_path = os.path.join(FILES_DIRECTORY, file_name)

    # Check if the file exists
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error:[/bold red] File '{file_name}' not found.")
        return

    # Use nano to edit the file (assuming it's available on the system)
    try:
        subprocess.run(["nano", file_path])
        console.print(f"[bold green]Editing '{file_name}' completed![/bold green]")
    except FileNotFoundError:
        console.print("[bold red]Error:[/bold red] 'nano' is not installed or not available on this system.")

def delete_file():
    """Delete a file."""
    file_name = Prompt.ask("[bold yellow]Enter the name of the file to delete[/bold yellow]").strip()
    file_path = os.path.join(FILES_DIRECTORY, file_name)

    # Check if the file exists
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error:[/bold red] File '{file_name}' not found.")
        return

    # Delete the file
    os.remove(file_path)
    console.print(f"[bold green]File '{file_name}' deleted successfully![/bold green]")

def execute():
    """Main function to execute file operations."""
    action = Prompt.ask(
        "[bold yellow]What would you like to do?[/bold yellow]",
        choices=["1. Create a file", "2. Edit a file", "3. Delete a file", "4. Exit"],
        show_choices=True
    )

    if action == "1":
        create_file()
    elif action == "2":
        edit_file()
    elif action == "3":
        delete_file()
    elif action == "4":
        console.print("[bold green]Exiting file manager...[/bold green]")
    else:
        console.print("[bold red]Invalid action. Please try again.[/bold red]")
