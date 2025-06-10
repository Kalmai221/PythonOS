#!/usr/bin/env python3
from rich.console import Console
from rich.prompt import IntPrompt
import sys
import subprocess
import pkg_resources
import shutil
from rich import box
from rich.panel import Panel

console = Console()
PACKAGE_NAME = "typing_test"
COMMAND_NAME = "tt"

def launch_typing_test(duration):
    """Run the typing test CLI with given duration."""
    try:
        subprocess.run([COMMAND_NAME, "-t", str(duration)], check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Typing test failed to start or ended with error.[/bold red]\n{e}")
        sys.exit(1)

def main():
    # Prompt for typing test duration
    time_sec = IntPrompt.ask(
        "[bold]How many seconds do you want to do the typing test for?[/bold] (e.g. 30, 60)",
        default=30,
        show_default=True,
        console=console,
    )

    if time_sec <= 0:
        console.print("[bold yellow]Duration must be a positive integer. Exiting.[/bold yellow]")
        sys.exit(0)

    console.print(f"[bold green]Starting typing test for {time_sec} seconds...[/bold green]\n")
    launch_typing_test(time_sec)

if __name__ == "__main__":
    main()

def execute():
    main()
