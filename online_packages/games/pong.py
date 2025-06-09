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

def check_package_installed(package_name):
    installed_packages = {pkg.key for pkg in pkg_resources.working_set}
    return package_name in installed_packages

def main():
    console.clear()
    header = Text("Pypong Installer", style="bold black on white", justify="center", no_wrap=True)
    console.print(Panel(header, style="white", box=box.ROUNDED, padding=(1, 4)))

    info = Text(
        "Easily install the [bold]pypong[/bold] package for your system.\n\n"
        "This installer will run:\n"
        "[green]python -m pip install pypong --user[/green]\n",
        style="dim",
        justify="center"
    )
    console.print(Panel(info, box=box.ROUNDED, padding=(1, 4), style="grey93"))

    package_name = "pypong"
    if check_package_installed(package_name):
        console.print(f"[bold green]{package_name} is already installed.[/bold green]")
    else:
        if not Confirm.ask("Do you want to proceed with the installation?", default=True):
            console.print("[bold yellow]Installation cancelled.[/bold yellow]")
            sys.exit(0)
        with console.status("[bold green]Installing pypong package...[/bold green]", spinner="dots"):
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", package_name, "--user", "--break-system-packages"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as e:
                console.print(Panel(f"[bold red]Installation failed![/bold red]\n\nError:\n{e.stderr}", style="red", box=box.ROUNDED, padding=(1, 2)))
                sys.exit(1)
            else:
                console.print(Panel("[bold green]Installation succeeded![/bold green]\n\nYou can now run [bold]pypong[/bold].", style="green", box=box.ROUNDED, padding=(1, 2)))

    console.print("[bold green]Launching Pypong...[/bold green]\n")
    try:
        subprocess.run(["pypong"], check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Pypong failed to start or ended with error.[/bold red]\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

def execute():
    main()