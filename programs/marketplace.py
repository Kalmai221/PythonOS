import os
import requests
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import IntPrompt
from rich import print

# === CONFIGURATION ===
REPO_OWNER = "Kalmai221"
REPO_NAME = "PythonOS"
GAMES_PATH = "online_packages/games"
API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{GAMES_PATH}"
INSTALL_DIR = Path("files/installed_games")

config = {
    "name": "marketplace",
    "description": "Download Packages from Online."
}

# Ensure the install directory exists
INSTALL_DIR.mkdir(parents=True, exist_ok=True)

console = Console()

def fetch_game_list():
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        console.print(f"[bold red]Failed to fetch game list: {e}[/bold red]")
        return []

def show_game_table(games):
    table = Table(title="🕹️ Available Games from Marketplace", header_style="bold blue")
    table.add_column("Index", justify="right")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="yellow")

    for idx, game in enumerate(games, start=1):
        table.add_row(str(idx), game["name"], game["type"])

    console.print(table)

def download_game(game):
    name = game["name"]
    download_url = game.get("download_url")

    if not download_url:
        console.print(f"[bold red]No download URL found for {name}[/bold red]")
        return

    try:
        response = requests.get(download_url)
        response.raise_for_status()
        save_path = INSTALL_DIR / name
        with open(save_path, "wb") as f:
            f.write(response.content)
        console.print(f"[bold green]✓ Downloaded '{name}' to {save_path}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Failed to download '{name}': {e}[/bold red]")

def execute():
    console.print("[bold cyan]📡 Connecting to the Game Marketplace...[/bold cyan]")
    games = fetch_game_list()
    if not games:
        console.print("[bold yellow]No games found in the marketplace.[/bold yellow]")
        return

    py_games = [g for g in games if g["type"] == "file" and g["name"].endswith(".py")]

    if not py_games:
        console.print("[bold yellow]No Python games available to download.[/bold yellow]")
        return

    show_game_table(py_games)

    choice = IntPrompt.ask("Enter the index of the game to download (0 to cancel)", default=0)

    if choice == 0:
        console.print("[bold]Cancelled.[/bold]")
        return

    if 1 <= choice <= len(py_games):
        download_game(py_games[choice - 1])
    else:
        console.print("[bold red]Invalid selection.[/bold red]")
