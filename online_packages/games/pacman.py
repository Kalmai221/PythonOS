#!/usr/bin/env python3
import subprocess
import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.text import Text
from rich import box
import shutil

console = Console()
PACKAGE_NAME = "pacm4cli"

def is_installed():
    return shutil.which(PACKAGE_NAME) is not None

def install_package():
    if not Confirm.ask(f"Install {PACKAGE_NAME} via apt? Requires sudo.", default=True):
        console.print("[bold yellow]Installation cancelled.[/bold yellow]")
        sys.exit(0)
    try:
        console.print(f"[bold green]Running: sudo apt install {PACKAGE_NAME}[/bold green]")
        subprocess.run(["sudo", "apt", "install", PACKAGE_NAME, "-y"], check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Installation failed with error:[/bold red]\n{e}")
        sys.exit(1)

def run_game():
    try:
        subprocess.run([PACKAGE_NAME], check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]{PACKAGE_NAME} failed to start or crashed.[/bold red]\n{e}")
        sys.exit(1)

def main():
    console.clear()
    header = Text(f"{PACKAGE_NAME} Installer", style="bold black on white", justify="center")
    console.print(Panel(header, box=box.ROUNDED, padding=(1,4)))

    if is_installed():
        console.print(f"[bold green]{PACKAGE_NAME} is already installed.[/bold green]")
    else:
        install_package()

    console.print(f"[bold green]Launching {PACKAGE_NAME}...[/bold green]\n")
    run_game()

if __name__ == "__main__":
    main()
