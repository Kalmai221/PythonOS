from pathlib import Path
import os
import requests
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm
from rich.progress import Progress, BarColumn, TextColumn
import time
from requests.exceptions import HTTPError

console = Console()
GITHUB_API_BASE = "https://api.github.com/repos/Kalmai221/PythonOS/contents"
IGNORE_FOLDERS = {".git", ".OSData"}

def get_github_files(path=""):
    url = f"{GITHUB_API_BASE}/{path}" if path else GITHUB_API_BASE
    response = requests.get(url)
    response.raise_for_status()
    items = response.json()

    files = []
    for item in items:
        if item["type"] == "dir":
            if item["name"] in IGNORE_FOLDERS:
                continue
            files.extend(get_github_files(item["path"]))
        elif item["type"] == "file":
            files.append(item)
    return files

def is_file_different(local_path: Path, download_url: str) -> bool:
    if not local_path.exists():
        return True
    try:
        remote_content = requests.get(download_url).content
        local_content = local_path.read_bytes()
        return local_content != remote_content
    except Exception:
        return True

def list_updates(files, base_path=Path.cwd()):
    updates = []
    for file_info in files:
        local_file = base_path / file_info["path"]
        if is_file_different(local_file, file_info["download_url"]):
            updates.append(file_info["path"])
    return updates

def download_file(local_path: Path, download_url: str):
    content = requests.get(download_url).content
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(content)

def apply_updates(files_to_update, all_files, base_path=Path.cwd()):
    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Updating files...", total=len(files_to_update))
        for path_str in files_to_update:
            file_info = next(f for f in all_files if f["path"] == path_str)
            local_file = base_path / file_info["path"]
            download_file(local_file, file_info["download_url"])
            progress.advance(task)
            time.sleep(0.1)

def show_update_table(files_to_update):
    table = Table(title="Files to Update", header_style="bold magenta")
    table.add_column("Index", justify="right")
    table.add_column("File Path", style="cyan")

    for i, filepath in enumerate(files_to_update, start=1):
        table.add_row(str(i), filepath)

    console.print(table)

def update_system(auto_update=False):
    base_path = Path.cwd()  # Detect current working directory dynamically
    console.print(f"[bold blue]Working directory detected as:[/bold blue] {base_path}\n")
    console.print("[bold cyan]Checking for updates...[/bold cyan]")
    try:
        files = get_github_files()
    except HTTPError as e:
        if e.response.status_code == 403:
            console.print("[bold red]GitHub API rate limit exceeded. Please try again later.[/bold red]")
        else:
            console.print(f"[bold red]Failed to fetch update info: {e}[/bold red]")
        return False
    except requests.RequestException as e:
        console.print(f"[bold red]Failed to fetch update info: {e}[/bold red]")
        return False

    files_to_update = list_updates(files, base_path)

    if not files_to_update:
        console.print("[bold green]Your system is up to date! 🎉[/bold green]")
        return False

    show_update_table(files_to_update)

    if auto_update or Confirm.ask("\nDo you want to update these files?"):
        apply_updates(files_to_update, files, base_path)
        console.print("[bold green]Update complete![/bold green]")
        return True
    else:
        console.print("[bold yellow]Update cancelled.[/bold yellow]")
        return False


if __name__ == "__main__":
    update_system()
