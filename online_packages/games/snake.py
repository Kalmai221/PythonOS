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
    console.print(Panel(Text("nsnake Installer", style="bold black on white", justify="center"), box=box.ROUNDED, padding=(1, 4)))
    console.print(Panel(
        "This will install the classic [bold]snake[/bold] game.\n\n"
        "[green]sudo apt install nsnake[/green]",
        style="grey93", box=box.ROUNDED, padding=(1, 4)
    ))

    if is_installed("nsnake"):
        console.print("[bold green]nsnake is already installed.[/bold green]")
    else:
        if not Confirm.ask("Install nsnake?", default=True):
            console.print("[bold yellow]Cancelled.[/bold yellow]")
            sys.exit(0)
        with console.status("[green]Installing nsnake...[/green]", spinner="dots"):
            subprocess.run(["sudo", "apt", "install", "-y", "nsnake"], check=True)

    console.print("\n[bold green]Launching nsnake...[/bold green]")
    subprocess.run(["nsnake"])

if __name__ == "__main__":
    main()
