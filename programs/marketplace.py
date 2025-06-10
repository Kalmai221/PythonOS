import requests
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import IntPrompt, Confirm
import hashlib
import sys

config = {
    "name": "marketplace",
    "description": "Download Packages from Online."
}

# === CONFIGURATION ===
REPO_OWNER = "Kalmai221"
REPO_NAME = "PythonOS"
BASE_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/online_packages"

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

def get_raw_url(item):
    # Convert API url to raw url for stable raw content fetching
    download_url = item.get("download_url")
    if download_url and "github.com" in download_url:
        download_url = download_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return download_url

def download_file(item, category, *, force=False):
    name = item["name"]
    raw_url = get_raw_url(item)
    if not raw_url:
        console.print(f"[bold red]No raw URL found for {name}[/bold red]")
        return False

    install_dir = Path(f"files/installed_{category}")
    install_dir.mkdir(parents=True, exist_ok=True)
    save_path = install_dir / name

    try:
        response = requests.get(raw_url)
        response.raise_for_status()
        remote_content = response.content
    except Exception as e:
        console.print(f"[bold red]Failed to download '{name}': {e}[/bold red]")
        return False

    if save_path.exists() and not force:
        try:
            with open(save_path, "rb") as f:
                local_content = f.read()
            if local_content == remote_content:
                console.print(f"[green]'{name}' is already up-to-date. Skipping download.[/green]")
                return False
            else:
                if not Confirm.ask(f"[yellow]'{name}' exists but differs from remote. Update it?[/yellow]", default=True):
                    console.print("[bold]Skipped update.[/bold]")
                    return False
        except Exception as e:
            console.print(f"[bold red]Failed to read existing file '{name}': {e}[/bold red]")
            return False

    try:
        with open(save_path, "wb") as f:
            f.write(remote_content)
        console.print(f"[bold green]✓ Downloaded '{name}' to {save_path}[/bold green]")
        return True
    except Exception as e:
        console.print(f"[bold red]Failed to write '{name}': {e}[/bold red]")
        return False

def show_table(title, items):
    table = Table(title=title, header_style="bold blue")
    table.add_column("Index", justify="right")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="yellow")
    for idx, item in enumerate(items, start=1):
        table.add_row(str(idx), item["name"], item["type"])
    console.print(table)

def list_installed_programs():
    base_path = Path("files")
    installed = []
    if not base_path.exists():
        return installed
    for cat_dir in base_path.glob("installed_*"):
        category = cat_dir.name.replace("installed_", "")
        for f in cat_dir.glob("*.py"):
            installed.append({
                "category": category,
                "name": f.name,
                "path": f
            })
    return installed

def download_program_flow():
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

def check_updates_flow():
    installed = list_installed_programs()
    if not installed:
        console.print("[yellow]No installed programs found to check for updates.[/yellow]")
        return

    # Group installed programs by category
    by_category = {}
    for prog in installed:
        by_category.setdefault(prog["category"], []).append(prog)

    any_updated = False

    for category, programs in by_category.items():
        console.print(f"\n[bold cyan]Checking updates in category '{category}'[/bold cyan]")
        remote_items = fetch_items_in_category(category)
        if not remote_items:
            console.print(f"[yellow]Failed to fetch remote items for category '{category}'. Skipping.[/yellow]")
            continue

        remote_map = {item["name"]: item for item in remote_items if item["type"] == "file"}

        for prog in programs:
            name = prog["name"]
            if name in remote_map:
                updated = download_file(remote_map[name], category)
                any_updated = any_updated or updated
            else:
                console.print(f"[yellow]'{name}' not found in remote category '{category}'.[/yellow]")

    if not any_updated:
        console.print("[green]All programs are up-to-date.[/green]")

def main_menu():
    while True:
        console.print("\n[bold magenta]Marketplace Menu[/bold magenta]")
        console.print("1. Download Programs")
        console.print("2. Check for Updates")
        console.print("3. Exit")
        choice = IntPrompt.ask("Choose an option", choices=["1", "2", "3"])

        if choice == 1:
            download_program_flow()
        elif choice == 2:
            check_updates_flow()
        elif choice == 3:
            console.print("Goodbye!")
            sys.exit(0)

if __name__ == "__main__":
    main_menu()

def execute():
    main_menu()