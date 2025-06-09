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
    console.print(Panel(Text("2048 Game Installer", style="bold black on white", justify="center"), box=box.ROUNDED, padding=(1, 4)))
    console.print(Panel(
        "This will install the terminal version of [bold]2048[/bold].\n\n"
        "[green]sudo apt install 2048[/green]",
        style="grey93", box=box.ROUNDED, padding=(1, 4)
    ))

    if is_installed("2048"):
        console.print("[bold green]2048 is already installed.[/bold green]")
    else:
        if not Confirm.ask("Install 2048?", default=True):
            console.print("[bold yellow]Cancelled.[/bold yellow]")
            sys.exit(0)
        with console.status("[green]Installing 2048...[/green]", spinner="dots"):
            subprocess.run(["sudo", "apt", "install", "-y", "2048"], check=True)

    console.print("\n[bold green]Launching 2048...[/bold green]")
    subprocess.run(["2048"])

if __name__ == "__main__":
    main()

def execute():
    main()
