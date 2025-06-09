#!/usr/bin/env python3
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Confirm, IntPrompt
from rich.spinner import Spinner
from rich.align import Align
from rich import box
import subprocess
import sys
import pkg_resources

console = Console()

def check_package_installed(package_name):
    """Check if a package is installed."""
    installed_packages = {pkg.key for pkg in pkg_resources.working_set}
    return package_name in installed_packages

def main():
    console.clear()
    # Header with big elegant typography
    header_text = Text("Typing Test Installer", style="bold black on white", justify="center", no_wrap=True)
    console.print(Panel(header_text, style="white", box=box.ROUNDED, padding=(1, 4)))

    # Subtext with neutral gray body text color and spacing
    subtext = Text(
        "Easily install the [bold]typing_test[/bold] package for your system.\n\n"
        "This installer will run:\n"
        "[green]python -m pip install typing_test --user[/green]\n",
        style="dim",
        justify="center"
    )
    console.print(Panel(subtext, box=box.ROUNDED, padding=(1, 4), style="grey93"))

    # Check if the package is already installed
    package_name = "typing_test"
    if check_package_installed(package_name):
        console.print(f"[bold green]{package_name} is already installed.[/bold green]")
    else:
        # Confirm install
        if not Confirm.ask("Do you want to proceed with the installation?", default=True):
            console.print("[bold yellow]Installation cancelled.[/bold yellow]")
            sys.exit(0)

        # Run installation with spinner
        with console.status("[bold green]Installing typing_test package...[/bold green]", spinner="dots") as status:
            try:
                # Run pip install command
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", package_name, "--user", "--break-system-packages"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                console.print(Panel(f"[bold red]Installation failed![/bold red]\n\nError:\n{e.stderr}", style="red", box=box.ROUNDED, padding=(1, 2)))
                sys.exit(1)
            else:
                console.print(Panel("[bold green]Installation succeeded![/bold green]\n\nYou can now use the typing_test package.", style="green", box=box.ROUNDED, padding=(1, 2)))

    # Ask how long to do the typing test for
    console.print()
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

    # Launch the typing test with desired time
    try:
        subprocess.run(
            ["tt", "-t", str(time_sec)],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Typing test failed to start or ended with error.[/bold red]\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
  
def execute():
  main()