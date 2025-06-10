import os
import sys
import subprocess
from pathlib import Path
import importlib.util
from rich.console import Console
from rich.table import Table
from rich.prompt import IntPrompt

console = Console()

config = {
    "name": "programs",
    "description": "Browse and launch installed programs from any category (games, multimedia, etc)."
}

ROOT_DIR = Path("files")

def list_installed_programs():
    programs = []
    for folder in ROOT_DIR.iterdir():
        if folder.is_dir() and folder.name.startswith("installed_"):
            category = folder.name.replace("installed_", "")
            for file in sorted(folder.glob("*.py")):
                programs.append((category, file))
    return programs

def import_program_module(filepath: Path):
    """Dynamically import a .py file as a module."""
    try:
        spec = importlib.util.spec_from_file_location(filepath.stem, str(filepath))
        if spec is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[filepath.stem] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        console.print(f"[bold red]Failed to import module {filepath.name}: {e}[/bold red]")
        return None

def execute():
    programs = list_installed_programs()
    if not programs:
        console.print(
            "[bold yellow]No installed programs found.[/bold yellow] "
            "[cyan]Visit the [bold]Marketplace[/bold] to download packages.[/cyan]"
        )
        return

    table = Table(title="Installed Programs", show_lines=True, header_style="bold cyan")
    table.add_column("Index", justify="right", style="bold")
    table.add_column("Program Name", style="green")
    table.add_column("Category", style="magenta")

    for idx, (category, path) in enumerate(programs, start=1):
        table.add_row(str(idx), path.stem, category)

    console.print(table)

    try:
        choice = IntPrompt.ask("Enter the index of the program to manage (0 to cancel)", default=0)
        if choice == 0:
            console.print("Cancelled.")
            return
        if choice < 1 or choice > len(programs):
            console.print("[bold red]Invalid selection.[/bold red]")
            return
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Cancelled by user.[/bold yellow]")
        return

    category, program_path = programs[choice - 1]

    # Ask if user wants to run or uninstall
    from rich.prompt import Prompt
    action = Prompt.ask(
        f"What do you want to do with [green]{program_path.stem}[/green]? (run/uninstall/cancel)",
        choices=["run", "uninstall", "cancel"],
        default="run"
    )

    if action == "cancel":
        console.print("Operation cancelled.")
        return

    if action == "uninstall":
        try:
            program_path.unlink()
            console.print(f"[bold red]Uninstalled {program_path.name}[/bold red]")

            # Remove category folder if empty
            category_folder = program_path.parent
            if not any(category_folder.iterdir()):
                category_folder.rmdir()
                console.print(f"[bold yellow]Removed empty category folder '{category_folder.name}'.[/bold yellow]")
        except Exception as e:
            console.print(f"[bold red]Failed to uninstall: {e}[/bold red]")
        return

    # Else, run the program
    console.print(f"[bold green]Launching:[/bold green] {program_path.name} from [magenta]{category}[/magenta]")

    mod = import_program_module(program_path)
    if mod is None:
        console.print("[bold red]Import error. Cannot launch program.[/bold red]")
        return

    if hasattr(mod, "execute") and callable(mod.execute):
        try:
            mod.execute()
            console.print("[bold green]Program exited successfully.[/bold green]")
        except Exception as e:
            console.print(f"[bold red]Program execution error:[/bold red] {e}")
    else:
        console.print(f"[bold red]Program does not have an executable 'execute()' function.[/bold red]")

if __name__ == "__main__":
    execute()
