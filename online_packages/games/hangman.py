#!/usr/bin/env python3
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Confirm
from rich import box
import subprocess
import sys
import importlib.util

console = Console()

def is_installed(module_name):
    """Check if a Python module is installed."""
    return importlib.util.find_spec(module_name) is not None

def main():
    console.clear()
    console.print(Panel(Text("Hangman Game Installer", style="bold black on white", justify="center"), box=box.ROUNDED, padding=(1, 4)))
    console.print(Panel(
        "This will install a Python-based [bold]Hangman[/bold] game using pip.\n\n"
        "[green]pip install hangman-game[/green]",
        style="grey93", box=box.ROUNDED, padding=(1, 4)
    ))

    if is_installed("hangman_game"):
        console.print("[bold green]hangman-game is already installed.[/bold green]")
    else:
        if not Confirm.ask("Install hangman-game via pip?", default=True):
            console.print("[bold yellow]Cancelled.[/bold yellow]")
            sys.exit(0)
        with console.status("[green]Installing hangman-game...[/green]", spinner="dots"):
            subprocess.run([sys.executable, "-m", "pip", "install", "--user", "hangman-game", "--break-system-packages"], check=True)

    console.print("\n[bold green]Launching hangman-game...[/bold green]")
    subprocess.run([sys.executable, "-m", "hangman_game"])

if __name__ == "__main__":
    main()

def execute():
    main()
