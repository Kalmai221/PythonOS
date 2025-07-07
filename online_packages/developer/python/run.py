import os
import importlib.util
import sys
from rich.console import Console
from rich.prompt import Prompt

console = Console()

# Attempt to import IPython
try:
    from IPython import start_ipython
    ipython_available = True
except ImportError:
    ipython_available = False

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
    current_directory = get_current_directory()
    if current_directory is None:
        return

    console.print("[bold green]Select mode:[/bold green]")
    console.print("1. Run a Python file.")
    console.print("2. Start IPython shell.")

    choice = Prompt.ask("Enter 1 or 2 [1/2]", choices=["1", "2"])

    if choice == "1":
        file_name = Prompt.ask("Enter Python file name (e.g., test.py)")
        file_path = os.path.join(current_directory, file_name)

        if os.path.isfile(file_path) and file_name.endswith(".py"):
            console.print(f"[bold green]Running Python file:[/bold green] {file_name}")
            try:
                spec = importlib.util.spec_from_file_location(file_name, file_path)
                script_module = importlib.util.module_from_spec(spec)

                if file_name in sys.modules:
                    console.print("[bold yellow]Reloading Python file to pick up changes...[/bold yellow]")
                    del sys.modules[file_name]

                if hasattr(script_module, "execute"):
                    spec.loader.exec_module(script_module)
                    script_module.execute()
                else:
                    console.print("[bold yellow]No 'execute' function found. Running file as a normal Python script...[/bold yellow]")
                    os.system(f'python "{file_path}"')
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {e}")
        else:
            console.print(f"[bold red]Error:[/bold red] File '{file_name}' not found or not a Python file.")
            files = [f for f in os.listdir(current_directory) if f.endswith(".py")]
            if files:
                console.print("[bold yellow]Available Python files in the current directory:[/bold yellow]")
                for file in files:
                    console.print(f"- {file}")
            else:
                console.print("[bold yellow]No Python files found in the current directory.[/bold yellow]")

    elif choice == "2":
        if ipython_available:
            console.print("[bold green]Starting IPython shell...[/bold green]")
            start_ipython(argv=[])
        else:
            console.print("[bold red]IPython is not installed.[/bold red]")
            console.print("[bold yellow]To install it, run the IPython installer from the 'programs' application.[/bold yellow]")
