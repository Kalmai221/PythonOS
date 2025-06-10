    #!/usr/bin/env python3
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm
    from rich.text import Text
    from rich import box
    import subprocess
    import sys
    import importlib.util

    console = Console()
    PACKAGE_NAME = "curses_snake"

    def is_installed():
        return importlib.util.find_spec(PACKAGE_NAME) is not None

    def main():
        console.clear()
        console.print(Panel(Text("Snake Game Installer", style="bold black on white", justify="center"), box=box.ROUNDED, padding=(1, 4)))
        console.print(Panel(
            "This will install the terminal [bold]snake[/bold] game using pip.\n\n"
            "[green]pip install curses-snake[/green]",
            style="grey93", box=box.ROUNDED, padding=(1, 4)
        ))

        if is_installed():
            console.print("[bold green]curses-snake is already installed.[/bold green]")
        else:
            if not Confirm.ask("Install curses-snake via pip?", default=True):
                console.print("[bold yellow]Cancelled.[/bold yellow]")
                sys.exit(0)
            with console.status("[green]Installing curses-snake...[/green]", spinner="dots"):
                subprocess.run([sys.executable, "-m", "pip", "install", "--user", "curses-snake", "--break-system-packages"], check=True)

        console.print("\n[bold green]Launching curses-snake...[/bold green]")
        # Run the game via python -m curses_snake
        subprocess.run([sys.executable, "-m", PACKAGE_NAME])

    if __name__ == "__main__":
        main()

    def execute():
        main()
