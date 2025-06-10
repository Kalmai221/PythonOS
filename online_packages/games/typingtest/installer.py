#!/usr/bin/env python3
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Confirm
from rich import box
import sys
import subprocess
import pkg_resources
import shutil

console = Console()
PACKAGE_NAME = "typing_test"
COMMAND_NAME = "tt"

def check_package_installed(name):
    """Check if pip package is installed or CLI command is available."""
    installed = {pkg.key for pkg in pkg_resources.working_set}
    return name in installed or shutil.which(COMMAND_NAME) is not None

def install_package(name):
    """Install the pip package."""
    with console.status(f"[bold green]Installing {name}...[/bold green]", spinner="dots"):
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", name, "--user", "--break-system-packages"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            console.print(Panel(f"[bold red]Installation failed![/bold red]\n\n{e.stderr}", style="red", box=box.ROUNDED, padding=(1, 2)))
            sys.exit(1)
        else:
            console.print(Panel(f"[bold green]{name} installed successfully![/bold green]", style="green", box=box.ROUNDED, padding=(1, 2)))

def main():
    console.clear()

    # Header
    console.print(Panel(Text("Typing Test Installer", style="bold black on white", justify="center"), box=box.ROUNDED, padding=(1, 4)))

    # Description
    console.print(Panel(
        f"Easily install the [bold]{PACKAGE_NAME}[/bold] package for your system.\n\n"
        f"This installer will run:\n[green]python -m pip install {PACKAGE_NAME} --user[/green]",
        style="grey93",
        box=box.ROUNDED,
        padding=(1, 4)
    ))

    if check_package_installed(PACKAGE_NAME):
        console.print(f"[bold green]{PACKAGE_NAME} is already installed.[/bold green]")
    else:
        if not Confirm.ask(f"Do you want to proceed with the installation of {PACKAGE_NAME}?", default=True):
            console.print("[bold yellow]Installation cancelled.[/bold yellow]")
            sys.exit(0)
        install_package(PACKAGE_NAME)

if __name__ == "__main__":
    main()

def execute():
    main()
