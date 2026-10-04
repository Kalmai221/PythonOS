import os
import subprocess
import sys
from rich.console import Console
from rich.prompt import Prompt

console = Console()


def get_current_directory():
    """Reads the shell's current directory from current_directory.txt."""
    try:
        with open("current_directory.txt", "r") as f:
            directory = f.read().strip()
    except FileNotFoundError:
        console.print("[bold red]Error:[/bold red] current_directory.txt file not found.")
        return None
    if not os.path.isdir(directory):
        console.print("[bold red]Error:[/bold red] Directory not found in current_directory.txt.")
        return None
    return directory


def main():
    """Run a Python file from the current directory, or start IPython."""
    current_directory = get_current_directory()
    if current_directory is None:
        return

    console.print("[bold green]Select mode:[/bold green]")
    console.print("1. Run a Python file.")
    console.print("2. Start IPython shell.")
    choice = Prompt.ask("Enter 1 or 2", choices=["1", "2"])

    if choice == "1":
        file_name = Prompt.ask("Enter Python file name (e.g., test.py)").strip()
        file_path = os.path.abspath(os.path.join(current_directory, file_name))
        if not (os.path.isfile(file_path) and file_name.endswith(".py")):
            console.print(f"[bold red]Error:[/bold red] File '{file_name}' not found or not a Python file.")
            files = [f for f in os.listdir(current_directory) if f.endswith(".py")]
            if files:
                console.print("[bold yellow]Python files in this directory:[/bold yellow]")
                for f in files:
                    console.print(f"- {f}")
            return
        console.print(f"[bold green]Running {file_name}[/bold green]\n")
        try:
            subprocess.run([sys.executable, file_path], cwd=current_directory)
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Interrupted.[/bold yellow]")
    else:
        try:
            from IPython import start_ipython
        except ImportError:
            console.print("[bold red]IPython is not installed.[/bold red]")
            console.print("[bold yellow]Install it with the IPython installer in 'run programs'.[/bold yellow]")
            return
        console.print("[bold green]Starting IPython shell...[/bold green]")
        start_ipython(argv=[])


if __name__ == "__main__":
    main()


def execute():
    main()
