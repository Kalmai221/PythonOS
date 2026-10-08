from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm

import pyos
from pyos import reportsend
from pyos.i18n import tr

console = Console()
config = {"name": "gh", "description": "The GitHub CLI, run in this terminal: gh issue list | gh auth login | gh --help (downloaded once, with your permission)"}

def sign_in_note():
    return "[dim]" + escape(tr("This computer has no web browser, so gh cannot open one: it shows a one-time code, and you approve it on another device "
                                "(your phone or another computer) at the address it prints. If it asks to open a browser, press Enter and carry on.")) + "[/dim]"


def execute(args=None):
    args = list(args or [])
    user = pyos.userinfo()[0]
    if not user:
        console.print("[bold red]" + escape(tr("gh: you are not logged in.")) + "[/bold red]")
        return False
    try:
        if not reportsend.ensure_gh(lambda question: Confirm.ask(question, default=True), console.print):
            console.print("[yellow]" + escape(tr("Nothing was downloaded, so gh cannot run.")) + "[/yellow]")
            return False
    except reportsend.SendError as e:
        console.print(f"[bold red]gh: {escape(str(e))}[/bold red]")
        return False
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]" + escape(tr("Cancelled.")) + "[/yellow]")
        return False
    if args[:2] == ["auth", "login"] or args[:2] == ["auth", "refresh"]:
        console.print(sign_in_note())
    try:
        code = reportsend.run_gh(args, user)
    except reportsend.SendError as e:
        console.print(f"[bold red]gh: {escape(str(e))}[/bold red]")
        return False
    except KeyboardInterrupt:
        console.print("\n[yellow]" + escape(tr("gh stopped.")) + "[/yellow]")
        return False
    return code == 0
