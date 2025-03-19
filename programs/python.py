import os
import importlib.util
import sys
from rich.console import Console
from rich.prompt import Prompt

console = Console()

# Metadata dictionary for the command
config = {
    "name": "python",
    "description": "Run a Python file or start a Python shell."
}

def get_current_directory():
    """Reads the current directory from the current_directory.txt file."""
    try:
        with open("current_directory.txt", "r") as f:
            directory = f.read().strip()
            if os.path.isdir(directory):
                return directory
            else:
                console.print("[bold red]Error:[/bold red] Directory not found in current_directory.txt.")
                return None
    except FileNotFoundError:
        console.print("[bold red]Error:[/bold red] current_directory.txt file not found.")
        return None

def execute(args=None):
    """Handles Python file execution or shell start."""
    current_directory = get_current_directory()  # Get current directory from file
    if current_directory is None:
        return  # Exit if directory is invalid

    # Ask user to choose between running a Python file or starting a Python shell
    console.print("[bold green]Select mode:[/bold green]")
    console.print("1. Run a Python file.")
    console.print("2. Start Python shell.")

    # Asking the user for choice using rich prompt
    choice = Prompt.ask("Enter 1 or 2 [1/2]", choices=["1", "2"])

    if choice == "1":
        # Option to run a Python file
        file_name = Prompt.ask("Enter Python file name (e.g., test.py)")

        # Build the full path for the file
        file_path = os.path.join(current_directory, file_name)

        if os.path.isfile(file_path) and file_name.endswith(".py"):
            console.print(f"[bold green]Running Python file:[/bold green] {file_name}")

            try:
                # Dynamically load the Python file
                spec = importlib.util.spec_from_file_location(file_name, file_path)
                script_module = importlib.util.module_from_spec(spec)

                # Reload the module by removing it from sys.modules (force re-import)
                if file_name in sys.modules:
                    console.print("[bold yellow]Reloading Python file to pick up changes...[/bold yellow]")
                    del sys.modules[file_name]

                # If the script has an 'execute' function, call it
                if hasattr(script_module, "execute"):
                    spec.loader.exec_module(script_module)
                    script_module.execute()
                else:
                    # If no 'execute' function, run the Python script using python filename.py
                    console.print(f"[bold yellow]No 'execute' function found. Running file as a normal Python script...[/bold yellow]")
                    os.system(f"python {file_path}")
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {e}")
        else:
            console.print(f"[bold red]Error:[/bold red] File '{file_name}' not found or not a Python file.")
            # Optionally, list available Python files in the current directory
            files = [f for f in os.listdir(current_directory) if f.endswith(".py")]
            if files:
                console.print("[bold yellow]Available Python files in the current directory:[/bold yellow]")
                for file in files:
                    console.print(f"- {file}")
            else:
                console.print("[bold yellow]No Python files found in the current directory.[/bold yellow]")

    elif choice == "2":
        # Option to start Python shell
        console.print("[bold green]Starting Python shell...[/bold green]")
        os.system("python")
