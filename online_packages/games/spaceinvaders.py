#!/usr/bin/env python3
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.text import Text
from rich import box
import subprocess
import shutil
import sys

console = Console()

def is_installed(cmd):
    return shutil.which(cmd) is not None

def main():
    console.clear()
    console.print(Panel(Text("nInvaders Installer", style="bold black on white", justify="center"), box=box.ROUNDED, padding=(1, 4)))
    console.print(Panel(
        "[bold]nInvaders[/bold] is a terminal Space Invaders clone.\n\n"
        "[green]sudo apt install ninvaders[/green]",
        style="grey93", box=box.ROUNDED, padding=(1, 4)
    ))

    if is_installed("ninvaders"):
        console.print("[bold green]ninvaders is already installed.[/bold green]")
    else:
        if not Confirm.ask("Install ninvaders?", default=True):
            console.print("[bold yellow]Cancelled.[/bold yellow]")
            sys.exit(0)
        with console.status("[green]Installing ninvaders...[/green]", spinner="dots"):
            subprocess.run(["sudo", "apt", "install", "-y", "ninvaders"], check=True)

    console.print("\n[bold green]Launching ninvaders...[/bold green]")
    subprocess.run(["ninvaders"])

if __name__ == "__main__":
    main()

def execute():
    main()