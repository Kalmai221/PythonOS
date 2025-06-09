    #!/usr/bin/env python3
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.prompt import Confirm, IntPrompt
    from rich import box
    import subprocess
    import sys
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

    def launch_typing_test(duration):
        """Run the typing test CLI with given duration."""
        try:
            subprocess.run([COMMAND_NAME, "-t", str(duration)], check=True)
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]Typing test failed to start or ended with error.[/bold red]\n{e}")
            sys.exit(1)

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
