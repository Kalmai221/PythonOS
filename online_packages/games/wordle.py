#!/usr/bin/env python3
import subprocess
import sys
import shutil
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.text import Text
from rich import box
import pkg_resources

console = Console()
PACKAGE_NAME = "wordle-cli"
COMMAND_NAME = "wordle"

def is_installed():
    return shutil.which(COMMAND_NAME) is not None

def install_package():
    if not Confirm.ask(f"Install {PACKAGE_NAME} via pip?", default=True):
        console.print("[bold yellow]Installation cancelled.[/bold yellow]")
        sys.exit(0)
    try:
        console.print(f"[bold green]Installing {PACKAGE_NAME}...[/bold green]")
        subprocess.run([sys.executable, "-m", "pip", "install", PACKAGE_NAME, "--user"], check=True)
    except subprocess.CalledProcessError as e:
        console.print(Panel(f"[bold red]Installation failed![/bold red]\n\nError:\n{e}", style="red", box=box.ROUNDED, padding=(1, 2)))
        sys.exit(1)

def run_game():
    try:
        subprocess.run([COMMAND_NAME], check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]{COMMAND_NAME} failed to start or crashed.[/bold red]\n{e}")
        sys.exit(1)

def main():
    console.clear()
    header = Text(f"{PACKAGE_NAME} Installer", style="bold black on white", justify="center")
    console.print(Panel(header, box=box.ROUNDED, padding=(1, 4)))

    if is_installed():
        console.print(f"[bold green]{COMMAND_NAME} is already installed.[/bold green]")
    else:
        install_package()

    console.print(f"[bold green]Launching {COMMAND_NAME}...[/bold green]\n")
    run_game()

if __name__ == "__main__":
    main()

def execute():
    main()