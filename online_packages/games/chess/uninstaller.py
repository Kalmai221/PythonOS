#!/usr/bin/env python3
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Confirm
from rich import box
import subprocess
import sys
import pkg_resources

console = Console()
package_name = "cli-chess"

def check_package_installed(name):
    """Check if the pip package is installed."""
    installed = {pkg.key for pkg in pkg_resources.working_set}
    return name in installed

def uninstall_package(name):
    """Uninstall the pip package."""
    with console.status(f"[bold red]Uninstalling {name}...[/bold red]", spinner="dots"):
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", name, "-y"],
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            console.print(Panel(f"[bold red]Uninstallation failed![/bold red]\n\n{e.stderr}", style="red", box=box.ROUNDED, padding=(1, 2)))
            sys.exit(1)
        else:
            console.print(Panel(f"[bold green]{name} uninstalled successfully![/bold green]", style="green", box=box.ROUNDED, padding=(1, 2)))

def main():
    console.clear()

    # Header
    console.print(Panel(Text("CLI Chess Uninstaller", style="bold black on white", justify="center"), box=box.ROUNDED, padding=(1, 4)))

    # Description
    console.print(Panel(
        "This will uninstall [bold]cli-chess[/bold] from your system.\n\n"
        "Command run:\n[red]python -m pip uninstall cli-chess -y[/red]",
        style="grey93",
        box=box.ROUNDED,
        padding=(1, 4)
    ))

    # Installation check
    if not check_package_installed(package_name):
        console.print(Panel(
            f"[bold yellow]{package_name} is not installed.[/bold yellow]\n\n"
            "Nothing to uninstall.",
            style="yellow",
            box=box.ROUNDED,
            padding=(1, 2)
        ))
        sys.exit(0)

    # Confirmation
    console.print(f"[bold red]Warning:[/bold red] This will permanently remove {package_name} from your system.")

    if not Confirm.ask(f"Are you sure you want to uninstall {package_name}?", default=False):
        console.print("[bold yellow]Uninstallation cancelled.[/bold yellow]")
        sys.exit(0)

    uninstall_package(package_name)
    console.print(f"\n[bold green]{package_name} has been completely removed from your system.[/bold green]")

if __name__ == "__main__":
    main()

def execute():
    main()