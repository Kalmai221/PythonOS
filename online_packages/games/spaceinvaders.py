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
    PACKAGE_NAME = "space-invaders"

    def is_installed():
        return importlib.util.find_spec(PACKAGE_NAME) is not None

    def main():
        console.clear()
        console.print(Panel(Text("Space Invaders Installer", style="bold black on white", justify="center"), box=box.ROUNDED, padding=(1, 4)))
        console.print(Panel(
            f"This will install the terminal-based [bold]Space Invaders[/bold] game.\n\n"
            f"[green]pip install {PACKAGE_NAME}[/green]",
            style="grey93", box=box.ROUNDED, padding=(1, 4)
        ))

        if is_installed():
            console.print(f"[bold green]{PACKAGE_NAME} is already installed.[/bold green]")
        else:
            if not Confirm.ask(f"Install {PACKAGE_NAME} via pip?", default=True):
                console.print("[bold yellow]Cancelled.[/bold yellow]")
                sys.exit(0)
            with console.status(f"[green]Installing {PACKAGE_NAME}...[/green]", spinner="dots"):
                subprocess.run([sys.executable, "-m", "pip", "install", "--user", PACKAGE_NAME, "--break-system-packages"], check=True)

        console.print(f"\n[bold green]Launching {PACKAGE_NAME}...[/bold green]")
        subprocess.run([sys.executable, "-m", PACKAGE_NAME])

    if __name__ == "__main__":
        main()

    def execute():
        main()
