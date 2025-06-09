#!/usr/bin/env python3
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Confirm
from rich import box
import subprocess
import sys
import shutil

console = Console()

def is_installed(cmd):
    return shutil.which(cmd) is not None

def main():
    console.clear()
    console.print(Panel(Text("Hangman Game Installer", style="bold black on white", justify="center"), box=box.ROUNDED, padding=(1, 4)))
    console.print(Panel(
        "This will install [bold]hangman[/bold] from the [italic]bsdgames[/italic] package.\n\n"
        "[green]sudo apt install bsdgames[/green]",
        style="grey93", box=box.ROUNDED, padding=(1, 4)
    ))

    if is_installed("hangman"):
        console.print("[bold green]hangman is already installed.[/bold green]")
    else:
        if not Confirm.ask("Install bsdgames?", default=True):
            console.print("[bold yellow]Cancelled.[/bold yellow]")
            sys.exit(0)
        with console.status("[green]Installing bsdgames...[/green]", spinner="dots"):
            subprocess.run(["sudo", "apt", "install", "-y", "bsdgames"], check=True)

    console.print("\n[bold green]Launching hangman...[/bold green]")
    subprocess.run(["hangman"])

if __name__ == "__main__":
    main()

def execute():
    main()
