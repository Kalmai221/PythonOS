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
    console.print(Panel(Text("Tetris Game Installer", style="bold black on white", justify="center"), box=box.ROUNDED, padding=(1, 4)))
    console.print(Panel(
        "This will install [bold]tetris[/bold] from the [italic]bsdgames[/italic] package.\n\n"
        "[green]sudo apt install bsdgames[/green]",
        style="grey93", box=box.ROUNDED, padding=(1, 4)
    ))

    if is_installed("tetris"):
        console.print("[bold green]tetris is already installed.[/bold green]")
    else:
        if not Confirm.ask("Install bsdgames?", default=True):
            console.print("[bold yellow]Cancelled.[/bold yellow]")
            sys.exit(0)
        with console.status("[green]Installing bsdgames...[/green]", spinner="dots"):
            subprocess.run(["sudo", "apt", "install", "-y", "bsdgames"], check=True)

    console.print("\n[bold green]Launching tetris...[/bold green]")
    subprocess.run(["tetris"])

if __name__ == "__main__":
    main()

def execute():
    main()
