#!/usr/bin/env python3
import subprocess
import sys
import importlib.util
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.text import Text
from rich import box

console = Console()
PACKAGE_NAME = "py_quiz"  # the module name used to check install
CLI_COMMAND = "py-quiz"    # the executable command to run

def is_installed():
    return importlib.util.find_spec(PACKAGE_NAME) is not None

def main():
    console.clear()
    console.print(Panel(Text("py-quiz Installer", style="bold black on white", justify="center"), box=box.ROUNDED, padding=(1, 4)))
    console.print(Panel(
        f"This will install the Python CLI quiz game.\n\n"
        f"[green]pip install py-quiz[/green]",
        style="grey93", box=box.ROUNDED, padding=(1, 4)
    ))

    if is_installed():
        console.print(f"[bold green]{PACKAGE_NAME} is already installed.[/bold green]")
    else:
        if not Confirm.ask(f"Install {PACKAGE_NAME} via pip?", default=True):
            console.print("[bold yellow]Cancelled.[/bold yellow]")
            sys.exit(0)
        with console.status(f"[green]Installing {PACKAGE_NAME}...[/green]", spinner="dots"):
            subprocess.run([sys.executable, "-m", "pip", "install", "--user", "py-quiz", "--break-system-packages"], check=True)

    console.print(f"\n[bold green]Launching {CLI_COMMAND}...[/bold green]")
    try:
        subprocess.run([CLI_COMMAND])
    except FileNotFoundError:
        console.print(f"[bold red]Failed to launch {CLI_COMMAND}. Make sure your PATH includes the user scripts directory.[/bold red]")

if __name__ == "__main__":
    main()

def execute():
    main()
