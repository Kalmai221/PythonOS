#!/usr/bin/env python3
from rich.console import Console
from rich.prompt import Confirm
from rich import box
from rich.panel import Panel
from rich.text import Text
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

def uninstall_package(name):
    """Uninstall the pip package."""
    with console.status(f"[bold red]Uninstalling {name}...[/bold red]", spinner="dots"):
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", name, "-y"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            console.print(Panel(f"[bold red]Uninstallation failed![/bold red]\n\n{e.stderr}", style="red", box=box.ROUNDED, padding=(1, 2)))
            sys.exit(1)
        else:
            console.print(Panel(f"[bold green]{name} uninstalled successfully![/bold green]", style="green", box=box.ROUNDED, padding=(1, 2)))

def main():
    console.clear()

    # Header
    console.print(Panel(Text("Typing Test Uninstaller", style="bold black on white", justify="center"), box=box.ROUNDED, padding=(1, 4)))

    # Description
    console.print(Panel(
        f"This uninstaller will remove the [bold]{PACKAGE_NAME}[/bold] package from your system.\n\n"
        f"This uninstaller will run:\n[red]python -m pip uninstall {PACKAGE_NAME} -y[/red]",
        style="grey93",
        box=box.ROUNDED,
        padding=(1, 4)
    ))

    if not check_package_installed(PACKAGE_NAME):
        console.print(f"[bold yellow]{PACKAGE_NAME} is not installed.[/bold yellow]")
        sys.exit(0)

    if not Confirm.ask(f"Do you want to proceed with the uninstallation of {PACKAGE_NAME}?", default=True):
        console.print("[bold yellow]Uninstallation cancelled.[/bold yellow]")
        sys.exit(0)

    uninstall_package(PACKAGE_NAME)

if __name__ == "__main__":
    main()

def execute():
    main()
