from rich.console import Console
from rich.markup import escape

import pyos
from pyos import reportsend

console = Console()
config = {"name": "gh", "description": "The GitHub CLI, run in this terminal: gh issue list | gh auth login | gh --help (installed with PythonOS)"}

SIGN_IN_NOTE = ("[dim]This computer has no web browser, so gh cannot open one: it shows a one-time code, and you approve it on "
                "[bold]another device[/bold] (your phone or another computer) at the address it prints. If it asks to open a browser, "
                "press Enter and carry on.[/dim]")


def execute(args=None):
    args = list(args or [])
    user = pyos.userinfo()[0]
    if not user:
        console.print("[bold red]gh: you are not logged in.[/bold red]")
        return False
    if not reportsend.gh_path():
        console.print("[bold red]gh: the GitHub CLI is not installed in this copy of PythonOS.[/bold red]")
        console.print(f"[dim]{escape(reportsend.install_hint())}[/dim]")
        return False
    if args[:2] == ["auth", "login"] or args[:2] == ["auth", "refresh"]:
        console.print(SIGN_IN_NOTE)
    try:
        code = reportsend.run_gh(args, user)
    except reportsend.SendError as e:
        console.print(f"[bold red]gh: {escape(str(e))}[/bold red]")
        return False
    except KeyboardInterrupt:
        console.print("\n[yellow]gh stopped.[/yellow]")
        return False
    return code == 0
