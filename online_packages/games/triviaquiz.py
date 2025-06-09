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
    console.print(Panel(Text("Quiz Game Installer", style="bold black on white", justify="center"), box=box.ROUNDED, padding=(1, 4)))
    console.print(Panel(
        "[bold]quiz[/bold] is part of the [italic]bsdgames[/italic] package.\n\n"
        "[green]sudo apt install bsdgames[/green]",
        style="grey93", box=box.ROUNDED, padding=(1, 4)
    ))

    if is_installed("quiz"):
        console.print("[bold green]quiz is already installed.[/bold green]")
    else:
        if not Confirm.ask("Install bsdgames?", default=True):
            console.print("[bold yellow]Cancelled.[/bold yellow]")
            sys.exit(0)
        with console.status("[green]Installing bsdgames...[/green]", spinner="dots"):
            subprocess.run(["sudo", "apt", "install", "-y", "bsdgames"], check=True)

    console.print("\n[bold green]Launching quiz...[/bold green]")
    subprocess.run(["quiz"])

if __name__ == "__main__":
    main()
