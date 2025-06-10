#!/usr/bin/env python3
from rich.console import Console
from rich.prompt import Confirm
import subprocess
import sys

console = Console()
packages = ["yt-dlp", "pygame"]

def uninstall(pkg):
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", pkg],
            check=True,
            capture_output=True,
            text=True
        )
        console.print(f"[green]{pkg} uninstalled.[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to uninstall {pkg}: {e.stderr}[/red]")

def main():
    console.print("[bold red]Uninstall YouTube Music Player dependencies[/bold red]")
    if Confirm.ask("Are you sure?", default=False):
        for pkg in packages:
            uninstall(pkg)
        console.print("[bold green]Uninstallation complete.[/bold green]")
    else:
        console.print("[yellow]Cancelled.[/yellow]")

if __name__ == "__main__":
    main()

def execute():
    main()