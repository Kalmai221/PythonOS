#!/usr/bin/env python3
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich import box
import subprocess
import sys
import pkg_resources

console = Console()
requirements = ["yt-dlp", "pygame"]

def check_installed(pkg):
    installed = {p.key for p in pkg_resources.working_set}
    return pkg.lower() in installed

def install(pkg):
    with console.status(f"[bold green]Installing {pkg}...[/bold green]", spinner="dots"):
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg, "--user"],
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            console.print(Panel(f"[bold red]Failed to install {pkg}[/bold red]\n\n{e.stderr}", style="red", box=box.ROUNDED))
            sys.exit(1)
        else:
            console.print(Panel(f"[bold green]{pkg} installed successfully![/bold green]", style="green", box=box.ROUNDED))

def main():
    console.clear()
    console.print(Panel("🎶 YouTube Music Player Installer", style="bold black on white", box=box.ROUNDED, padding=(1, 4)))

    for pkg in requirements:
        if not check_installed(pkg):
            if Confirm.ask(f"Do you want to install [cyan]{pkg}[/cyan]?", default=True):
                install(pkg)
            else:
                console.print(f"[yellow]{pkg} was skipped. Some features may not work.[/yellow]")

    console.print("[bold green]All packages installed. You can now run the music player with:[/bold green] [cyan]python run.py[/cyan]")

if __name__ == "__main__":
    main()

def execute():
    main()