#!/usr/bin/env python3
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box
import subprocess
import sys
import shutil

console = Console()
command_name = "cli-chess"

def check_command_available(cmd):
    """Check if the command is available in PATH."""
    return shutil.which(cmd) is not None

def launch_game(cmd):
    """Launch the CLI game."""
    try:
        subprocess.run([cmd], check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]{cmd} failed to start or crashed.[/bold red]\n{e}")
        sys.exit(1)
    except FileNotFoundError:
        console.print(f"[bold red]{cmd} not found![/bold red] Make sure cli-chess is installed.")
        sys.exit(1)

def main():
    console.clear()

    # Header
    console.print(Panel(Text("CLI Chess Launcher", style="bold black on white", justify="center"), box=box.ROUNDED, padding=(1, 4)))

    # Check if command is available
    if not check_command_available(command_name):
        console.print(Panel(
            f"[bold red]{command_name} not found![/bold red]\n\n"
            "Please install cli-chess first using:\n"
            "[green]python -m pip install cli-chess --user[/green]",
            style="red",
            box=box.ROUNDED,
            padding=(1, 2)
        ))
        sys.exit(1)

    console.print(f"[bold green]Launching {command_name}...[/bold green]\n")
    launch_game(command_name)

if __name__ == "__main__":
    main()

def execute():
    main()