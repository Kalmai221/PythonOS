import requests
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import IntPrompt, Confirm
import zipfile
import io
import hashlib
import pyos
import socket
import json
import shutil

config = {
    "name": "marketplace",
    "description": "Download Packages from Online."
}

# === CONFIGURATION ===
REPO_OWNER = "Kalmai221"
REPO_NAME = "PythonOS"
BASE_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/online_packages"

console = Console()

def check_internet(host="api.github.com", port=443, timeout=3):
    """Check if machine can connect to GitHub API."""
    try:
        socket.create_connection((host, port), timeout=timeout)
        return True
    except (socket.timeout, socket.gaierror, OSError):
        return False

def fetch_categories():
    try:
        response = requests.get(BASE_API_URL)
        response.raise_for_status()
        entries = response.json()
        return [entry for entry in entries if entry["type"] == "dir"]
    except Exception as e:
        console.print(f"[bold red]Failed to fetch categories: {e}[/bold red]")
        return []

def fetch_items_in_category(remote_path):
    url = f"{BASE_API_URL}/{remote_path}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        items = response.json()
        return items
    except Exception as e:
        console.print(f"[bold red]Failed to fetch items from '{remote_path}': {e}[/bold red]")
        return []

def get_raw_url(item):
    download_url = item.get("download_url")
    if download_url and "github.com" in download_url:
        download_url = download_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return download_url

def calculate_file_hash(file_path):
    """Calculates the SHA256 hash of a file."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(4096)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        console.print(f"[bold red]Failed to calculate hash for '{file_path}': {e}[/bold red]")
        return None

def download_file(item, category, install_dir, *, force=False):
    name = item["name"]
    raw_url = get_raw_url(item)
    if not raw_url:
        console.print(f"[bold red]No raw URL found for {name}[/bold red]")
        return False

    save_path = install_dir / name

    try:
        response = requests.get(raw_url)
        response.raise_for_status()
        remote_content = response.content
    except Exception as e:
        console.print(f"[bold red]Failed to download '{name}': {e}[/bold red]")
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
        for program_dir in cat_dir.glob("*"):
            if program_dir.is_dir():
                installed.append({
                    "category": category,
                    "name": program_dir.name,
                    "path": program_dir
                })
    return installed

def recursively_download_folder(remote_path, local_path, category):
    items = fetch_items_in_category(remote_path)
    if not items:
        console.print(f"[yellow]No items found in remote path '{remote_path}'[/yellow]")
        return

    for item in items:
        if item["type"] == "file":
            console.print(f"Downloading file: {item['name']} from {item.get('download_url')}")
            download_file(item, category, local_path)
        elif item["type"] == "dir":
            subdir_name = item["name"]
            new_local_subdir = local_path / subdir_name
            new_local_subdir.mkdir(parents=True, exist_ok=True)
            console.print(f"[bold green]✓ Created subdirectory '{subdir_name}' in {local_path}[/bold green]")
            recursively_download_folder(f"{remote_path}/{subdir_name}", new_local_subdir, category)

def download_program_flow():
    if not check_internet():
        console.print("[bold red]No internet connection detected. Please connect and try again.[/bold red]")
        return

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
    directories = [item for item in items if item["type"] == "dir"]

    if not directories:
        console.print(f"[bold yellow]No directories found in category '{category}'.[/bold yellow]")
        return

    show_table(f"📦 Available Directories in '{category}'", directories)
    dir_choice = IntPrompt.ask("Enter the index of the directory to download (0 to cancel)", default=0)

    if dir_choice == 0:
        console.print("[bold]Cancelled.[/bold]")
        return

    if 1 <= dir_choice <= len(directories):
        directory = directories[dir_choice - 1]
        directory_name = directory["name"]
        install_dir = Path(f"files/installed_{category}")
        install_dir.mkdir(parents=True, exist_ok=True)
        new_directory_path = install_dir / directory_name
        new_directory_path.mkdir(parents=True, exist_ok=True)
        console.print(f"[bold green]✓ Created directory '{directory_name}' in {install_dir}[/bold green]")

        recursively_download_folder(f"{category}/{directory_name}", new_directory_path, category)

        data_json_path = new_directory_path / "data.json"
        if data_json_path.exists():
            try:
                with open(data_json_path, "r") as f:
                    data = json.load(f)
                requires_restart = str(data.get("requires_restart_on_download", "false")).lower()
                if requires_restart == "true":
                    console.print("\n[bold yellow]⚠️ This package requires a restart of the OS to register new commands.[/bold yellow]")
                    restart_confirm = Confirm.ask("Would you like to restart now?")
                    if restart_confirm:
                        pyos.system("restart")
                    else:
                        console.print("[bold yellow]Remember to restart later for changes to take effect.[/bold yellow]")
            except Exception as e:
                console.print(f"[bold red]Failed to read/parse data.json for restart info: {e}[/bold red]")
        else:
            console.print("[bold yellow]Warning: data.json not found after download; unable to check restart requirement.[/bold yellow]")
    else:
        console.print("[bold red]Invalid directory selection.[/bold red]")

def uninstall_package_flow():
    installed = list_installed_programs()
    if not installed:
        console.print("[yellow]No installed programs found to uninstall.[/yellow]")
        return

    table = Table(title="Installed Packages", header_style="bold blue")
    table.add_column("Index", justify="right")
    table.add_column("Category", style="cyan")
    table.add_column("Name", style="green")
    for idx, pkg in enumerate(installed, start=1):
        table.add_row(str(idx), pkg["category"], pkg["name"])
    console.print(table)

    choice = IntPrompt.ask("Enter the index of the package to uninstall (0 to cancel)", default=0)
    if choice == 0:
        console.print("[bold]Cancelled.[/bold]")
        return

    if not (1 <= choice <= len(installed)):
        console.print("[bold red]Invalid selection.[/bold red]")
        return

    pkg = installed[choice - 1]
    pkg_path = pkg["path"]
    data_json_path = pkg_path / "data.json"

    if not data_json_path.exists():
        console.print(f"[bold red]data.json not found in {pkg_path}. Cannot proceed with uninstallation.[/bold red]")
        return

    try:
        with open(data_json_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        console.print(f"[bold red]Failed to read data.json: {e}[/bold red]")
        return

    uninstaller_script = data.get("scripts", {}).get("uninstaller")
    if not uninstaller_script:
        console.print("[bold yellow]No uninstaller script defined. Skipping uninstallation script step.[/bold yellow]")
    else:
        uninstaller_path = pkg_path / uninstaller_script
        if not uninstaller_path.exists():
            console.print(f"[bold red]Uninstaller script '{uninstaller_script}' not found in package folder.[/bold red]")
            return

        console.print(f"[bold green]Running uninstaller script: {uninstaller_script}[/bold green]")
        ret_code = os.system(f'python "{uninstaller_path}"')
        if ret_code != 0:
            console.print(f"[bold red]Uninstaller script exited with code {ret_code}. Aborting deletion.[/bold red]")
            return

    try:
        shutil.rmtree(pkg_path)
        console.print(f"[bold green]Successfully uninstalled and removed package '{pkg['name']}'.[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Failed to delete package folder: {e}[/bold red]")


def check_updates_flow():
    if not check_internet():
        console.print("[bold red]No internet connection detected. Please connect and try again.[/bold red]")
        return

    installed = list_installed_programs()
    if not installed:
        console.print("[yellow]No installed programs found to check for updates.[/yellow]")
        return

    any_updated = False

    for program in installed:
        category = program["category"]
        program_name = program["name"]
        install_dir = program["path"]

        console.print(f"\n[bold cyan]Checking updates for '{program_name}' in category '{category}'[/bold cyan]")

        remote_items = fetch_items_in_category(f"{category}/{program_name}")

        if not remote_items:
            console.print(f"[yellow]Failed to fetch remote items for '{program_name}' in category '{category}'. Skipping.[/yellow]")
            continue

        remote_files = {item["name"]: item for item in remote_items if item["type"] == "file"}

        for local_file in install_dir.glob("*"):
            if local_file.is_file():
                remote_item = remote_files.get(local_file.name)

                if remote_item:
                    remote_url = get_raw_url(remote_item)
                    if not remote_url:
                        console.print(f"[yellow]No raw URL found for remote file '{local_file.name}'. Skipping.[/yellow]")
                        continue

                    local_hash = calculate_file_hash(local_file)

                    try:
                        response = requests.get(remote_url)
                        response.raise_for_status()
                        remote_content = response.content
                        remote_hash = hashlib.sha256(remote_content).hexdigest()
                    except Exception as e:
                        console.print(f"[bold red]Failed to fetch remote content for '{local_file.name}': {e}[/bold red]")
                        continue

                    if local_hash and remote_hash and local_hash != remote_hash:
                        console.print(f"[yellow]'{local_file.name}' has changed. Downloading update.[/yellow]")
                        if download_file(remote_item, category, install_dir):
                            any_updated = True
                    else:
                        console.print(f"[green]'{local_file.name}' is up-to-date.[/green]")
                else:
                    console.print(f"[yellow]'{local_file.name}' exists locally but not remotely. It might be an orphaned file.[/yellow]")

        for remote_file_name, remote_item in remote_files.items():
            if not (install_dir / remote_file_name).exists():
                console.print(f"[yellow]New file '{remote_file_name}' found remotely. Downloading.[/yellow]")
                if download_file(remote_item, category, install_dir):
                    any_updated = True

    if not any_updated:
        console.print("[green]All programs are up-to-date.[/green]")

def main_menu():
    if not check_internet():
        console.print("[bold red]No internet connection detected. Marketplace requires internet access.[/bold red]")
        return

    while True:
        console.print("\n[bold magenta]Marketplace Menu[/bold magenta]")
        console.print("1. Download Programs")
        console.print("2. Check for Updates")
        console.print("3. Uninstall a Package")
        console.print("4. Exit")
        choice = IntPrompt.ask("Choose an option", choices=["1", "2", "3", "4"])

        if choice == 1:
            download_program_flow()
        elif choice == 2:
            check_updates_flow()
        elif choice == 3:
            uninstall_package_flow()
        elif choice == 4:
            console.print("Goodbye!")
            break

if __name__ == "__main__":
    main_menu()

def execute():
    main_menu()
