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
BASE_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/online_packages"

config = {
    "name": "marketplace",
    "description": "Download Packages from Online."
}

console = Console()

def fetch_categories():
    try:
        response = requests.get(BASE_API_URL)
        response.raise_for_status()
        entries = response.json()
        return [entry for entry in entries if entry["type"] == "dir"]
    except Exception as e:
        console.print(f"[bold red]Failed to fetch categories: {e}[/bold red]")
        return []

def fetch_items_in_category(category):
    try:
        url = f"{BASE_API_URL}/{category}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        console.print(f"[bold red]Failed to fetch items for '{category}': {e}[/bold red]")
        return []

def show_table(title, items):
    table = Table(title=title, header_style="bold blue")
    table.add_column("Index", justify="right")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="yellow")

    for idx, item in enumerate(items, start=1):
        table.add_row(str(idx), item["name"], item["type"])

    console.print(table)

def download_file(item, category):
    name = item["name"]
    download_url = item.get("download_url")

    if not download_url:
        console.print(f"[bold red]No download URL found for {name}[/bold red]")
        return

    install_dir = Path(f"files/installed_{category}")
    install_dir.mkdir(parents=True, exist_ok=True)
    save_path = install_dir / name

    try:
        response = requests.get(download_url)
        response.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(response.content)
        console.print(f"[bold green]✓ Downloaded '{name}' to {save_path}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Failed to download '{name}': {e}[/bold red]")

def execute():
    console.print("[bold cyan]📡 Connecting to the Marketplace...[/bold cyan]")

    # Step 1: Choose Category
    categories = fetch_categories()
    if not categories:
        console.print("[bold yellow]No categories found.[/bold yellow]")
        return

    show_table("📁 Available Categories", categories)
    category_choice = IntPrompt.ask("Enter the index of the category to browse (0 to cancel)", default=0)

    if category_choice == 0:
        console.print("[bold]Cancelled.[/bold]")
        return

    if not (1 <= category_choice <= len(categories)):
        console.print("[bold red]Invalid category selection.[/bold red]")
        return

    category = categories[category_choice - 1]["name"]

    # Step 2: Show files in that category
    items = fetch_items_in_category(category)
    py_files = [item for item in items if item["type"] == "file" and item["name"].endswith(".py")]

    if not py_files:
        console.print(f"[bold yellow]No Python files found in category '{category}'.[/bold yellow]")
        return

    show_table(f"📦 Available Files in '{category}'", py_files)
    file_choice = IntPrompt.ask("Enter the index of the file to download (0 to cancel)", default=0)

    if file_choice == 0:
        console.print("[bold]Cancelled.[/bold]")
        return

    if 1 <= file_choice <= len(py_files):
        download_file(py_files[file_choice - 1], category)
    else:
        console.print("[bold red]Invalid file selection.[/bold red]")

