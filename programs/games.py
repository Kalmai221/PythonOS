import os
import sys
import subprocess
from pathlib import Path
import importlib.util

import pyos
from rich.console import Console
from rich.table import Table
from rich.prompt import IntPrompt

console = Console()

config = {
    "name": "games",
    "description": "Displays all games downloaded on the system and provides the option to play them."
}

GAMES_DIR = Path("files/installed_games")

def list_games():
    if not GAMES_DIR.exists() or not GAMES_DIR.is_dir():
        return []
    # List .py files only
    games = [f for f in sorted(GAMES_DIR.iterdir()) if f.is_file() and f.suffix == ".py"]
    return games

def import_game_module(filepath: Path):
    """
    Dynamically imports the python file at filepath as a module,
    returns the module object or None if failed.
    """
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
    info = pyos.userinfo()
    username = info[0]
    games = list_games()
    if not games:
        console.print("[bold yellow]No installed games found in 'files/installed_games'.[/bold yellow]")
        return

    table = Table(title="Installed Games", show_lines=True, show_header=True, header_style="bold cyan")
    table.add_column("Index", justify="right", style="bold")
    table.add_column("Game Name", justify="left")

    for idx, game_path in enumerate(games, start=1):
        table.add_row(str(idx), game_path.stem)

    console.print(table)

    try:
        choice = IntPrompt.ask("Enter the index of the game to play ('0' to cancel)", default=0)
        if choice == 0:
            console.print("Cancelled game launch.")
            return
        if choice < 1 or choice > len(games):
            console.print("[bold red]Invalid selection.[/bold red]")
            return
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Cancelled by user.[/bold yellow]")
        return

    game_to_run = games[choice - 1]

    console.print(f"[bold green]Launching:[/bold green] {game_to_run.name}")

    mod = import_game_module(game_to_run)
    if mod is None:
        console.print("[bold red]Cannot launch the selected game due to import error.[/bold red]")
        return

    # Call the execute function if it exists
    if hasattr(mod, "execute") and callable(mod.execute):
        try:
            mod.execute()
            console.print("[bold green]Game exited successfully.[/bold green]")
        except Exception as e:
            console.print(f"[bold red]Game execution error:[/bold red] {e}")
    else:
        console.print(f"[bold red]Selected game does not have an executable 'execute()' function.[/bold red]")

if __name__ == "__main__":
    execute()
