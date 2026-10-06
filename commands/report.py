import time

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

import pyos.fs as fs
from pyos import report, settings

console = Console()
config = {"name": "report", "description": "Prepare a problem report you can read first, then send as a GitHub issue or save to a file."}


def _open_link(link):
    """Try to open the link in a browser; True if the system says it did (never on a locked-down system)."""
    try:
        from pyos import lockdown
        if lockdown.enabled():
            return False
        import webbrowser
        return bool(webbrowser.open(link))
    except Exception:
        return False


def execute(args=None):
    args = list(args or [])
    text = " ".join(a for a in args if not a.startswith("-"))
    waiting = None
    try:
        if "--pending" in args:
            found = report.pending()
            if not found:
                console.print("[green]No crash reports are waiting.[/green]")
                return True
            waiting = found[-1][1]
            title, body = report.read_pending(waiting)
            console.print(f"[dim]{len(found)} waiting; this is the newest ({escape(found[-1][0])}). It was written when PythonOS crashed, so it works without a network.[/dim]")
        else:
            if not text:
                text = Prompt.ask("What went wrong? (one or two sentences, or leave blank)", default="")
            body = report.redact(report.build(text, include_log="--no-log" not in args))
            title = text.strip().splitlines()[0][:70] if text.strip() else "Problem report"
        console.print(Panel(escape(body), title="[bold]This is everything the report contains[/bold]", border_style="blue"))
        console.print("[dim]Names, home folders, email and IP addresses were replaced. Nothing is sent unless you choose below.[/dim]")
        relay = str(settings.get("report_relay") or "")
        choices = ["l", "f", "n"] + (["s"] if relay else [])
        label = "(l)ink to open on GitHub, (f)ile, " + ("(s)end through the relay, " if relay else "") + "(n)o"
        pick = Prompt.ask(f"What would you like to do? {label}", choices=choices, default="f")
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled. Nothing was sent.[/yellow]")
        return False

    stamp = time.strftime("%Y%m%d-%H%M%S")
    if waiting and pick == "n":
        console.print("[yellow]Nothing was sent. The report stays in the waiting list.[/yellow]")
        return True
    if pick in ("l", "f"):
        path = fs.resolve(f"~/problem-report-{stamp}.txt", write=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        console.print(f"[green]Saved the report as {escape(fs.display(path, tilde=True))}.[/green]")
    if pick == "l":
        link = report.issue_link(title, body)
        if _open_link(link):
            console.print("[green]Opened GitHub in your browser. Check the text and press 'Submit new issue'.[/green]")
        else:
            console.print("Open this address on any device (it fills the issue in for you):")
            console.print(f"[bold cyan]{escape(link)}[/bold cyan]", soft_wrap=True)
            console.print(f"[dim]Or open {report.ISSUE_URL} and paste the saved file.[/dim]")
    elif pick == "s":
        try:
            if not Confirm.ask(f"Send this report to {escape(relay)}?", default=False):
                console.print("[yellow]Not sent.[/yellow]")
                return False
            console.print(f"[green]Sent. {escape(report.send_via_relay(relay, title, body))}[/green]")
        except Exception as e:
            console.print(f"[bold red]Could not send: {escape(str(e))}[/bold red]  (use the file option instead)")
            return False
    else:
        console.print("[yellow]Nothing was sent or saved.[/yellow]")
    if waiting and pick in ("l", "f", "s"):
        report.finish_pending(waiting)                 # handled: it leaves the waiting list
    return True
