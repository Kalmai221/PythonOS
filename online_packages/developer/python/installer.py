#!/usr/bin/env python3
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Confirm
from rich import box
import subprocess
import sys
import pkg_resources
import shutil

console = Console()
package_name = "ipython"

def check_package_installed(name):
    """Check if the pip package is installed."""
    installed = {pkg.key for pkg in pkg_resources.working_set}
    return name in installed or shutil.which(name) is not None

def install_package(name):
    """Install the pip package."""
    with console.status(f"[bold green]Installing {name}...[/bold green]", spinner="dots"):
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", name, "--user", "--break-system-packages"],
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            console.print(Panel(f"[bold red]Installation failed![/bold red]\n\n{e.stderr}", style="red", box=box.ROUNDED, padding=(1, 2)))
            sys.exit(1)
        else:
            console.print(Panel(f"[bold green]{name} installed successfully![/bold green]", style="green", box=box.ROUNDED, padding=(1, 2)))

def main():
    console.clear()

    # Header
    console.print(Panel(Text("Python Installer", style="bold black on white", justify="center"), box=box.ROUNDED, padding=(1, 4)))

    # Description
    console.print(Panel(
        "This installer will help you install [bold]ipython[/bold].\n\n"
        "Command run:\n[green]python -m pip install ipython --user[/green]",
        style="grey93",
        box=box.ROUNDED,
        padding=(1, 4)
    ))

    # Installation check
    if check_package_installed(package_name):
        console.print(f"[bold green]{package_name} is already installed.[/bold green]")
    else:
        if not Confirm.ask("Do you want to install ipython?", default=True):
            console.print("[bold yellow]Installation cancelled.[/bold yellow]")
            sys.exit(0)
        install_package(package_name)

    console.print(f"\n[bold green]{package_name} installation complete![/bold green]")
    console.print(f"You can now run it with: [bold cyan]ipython[/bold cyan]")

if __name__ == "__main__":
    main()

def execute():
    main()