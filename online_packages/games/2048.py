#!/usr/bin/env python3
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Confirm
from rich import box
import subprocess
import sys
import shutil
import importlib.util

console = Console()

def is_installed(module_name):
    """Check if a Python module is installed."""
    return importlib.util.find_spec(module_name) is not None

def main():
    console.clear()
    console.print(Panel(Text("2048 Game Installer", style="bold black on white", justify="center"), box=box.ROUNDED, padding=(1, 4)))
    console.print(Panel(
        "This will install the terminal version of [bold]2048[/bold] using pip.\n\n"
        "[green]pip install term2048[/green]",
        style="grey93", box=box.ROUNDED, padding=(1, 4)
    ))

    if is_installed("term2048"):
        console.print("[bold green]term2048 is already installed.[/bold green]")
    else:
        if not Confirm.ask("Install term2048 via pip?", default=True):
            console.print("[bold yellow]Cancelled.[/bold yellow]")
            sys.exit(0)
        with console.status("[green]Installing term2048...[/green]", spinner="dots"):
            subprocess.run([sys.executable, "-m", "pip", "install", "--user", "term2048", "--break-system-packages"], check=True)

    console.print("\n[bold green]Launching term2048...[/bold green]")
    subprocess.run([sys.executable, "-m", "term2048"])

if __name__ == "__main__":
    main()

def execute():
    main()
