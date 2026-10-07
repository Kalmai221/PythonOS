import time

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

import pyos
import pyos.fs as fs
from pyos import report, reportsend, settings

console = Console()
config = {"name": "report", "description": "Prepare a problem report you can read first, then send it (GitHub, Discord) or save it: report [what went wrong] | report status [number]"}


def _status(args):
    """report status [number]: what became of a report that was sent, from the public issue (no sign-in needed)."""
    wanted = args[0] if args else None
    if wanted is None:
        sent = reportsend.recorded()
        if not sent:
            console.print("No report has been sent from this PythonOS yet. Use report status <issue number> for any issue.")
            return True
        for item in sent[-10:]:
            console.print(f"  #{item['number']}  {escape(item['title'])}  [dim]{time.strftime('%Y-%m-%d', time.localtime(item['time']))}[/dim]")
        wanted = str(sent[-1]["number"])
        console.print(f"[dim]Showing the newest, #{wanted}.[/dim]")
    if not wanted.lstrip("#").isdigit():
        console.print("[bold red]Usage:[/bold red] report status [issue number]")
        return False
    try:
        info = reportsend.status_of(wanted.lstrip("#"))
    except reportsend.SendError as e:
        console.print(f"[bold red]{escape(str(e))}[/bold red]")
        return False
    console.print(f"[bold]#{wanted.lstrip('#')} {escape(info['title'])}[/bold]  - {escape(info['state'])}")
    console.print(f"[dim]To reply, type {escape(info['url'])} into a browser on another device.[/dim]")
    for who, text in info["comments"]:
        console.print(Panel(escape(text.strip()[:1500]), title=escape(who), border_style="blue", expand=False))
    if not info["comments"]:
        console.print("[dim]No replies yet.[/dim]")
    return True


def _send_github(title, body):
    """Post the report as a GitHub issue with the GitHub CLI (gh), signing the person in first if needed. True if it was created."""
    user = pyos.userinfo()[0]
    was_signed_in = False
    try:
        if not reportsend.ensure_gh(lambda question: Confirm.ask(question, default=True), console.print):
            console.print("[yellow]Nothing was downloaded, so nothing was posted.[/yellow]")
            return False
        was_signed_in = reportsend.gh_signed_in(user)
        if not was_signed_in:
            console.print(Panel("This computer has no web browser, so do the sign-in on [bold]another device[/bold] (your phone or another computer):\n"
                                "  1. GitHub's tool is about to show a one-time code. If it asks to open a browser, press Enter: it cannot, and carries on.\n"
                                "  2. On the other device open [bold cyan]https://github.com/login/device[/bold cyan], sign in if it asks, and type the code.\n"
                                "  3. Approve it. Then come back here: the report is posted by itself.\n"
                                "[dim]Press Ctrl+C to stop.[/dim]", title="[bold]Sign in to GitHub[/bold]", border_style="green", expand=False))
            reportsend.gh_login(user)
        with console.status("Creating the issue..."):
            issue = reportsend.gh_create_issue(user, title, body)
        stay = was_signed_in or Confirm.ask("Stay signed in to GitHub on this account for next time? (gh auth logout removes it)", default=False)
        if not stay:
            reportsend.gh_forget(user)
            console.print("[dim]The sign-in was deleted from this computer.[/dim]")
    except reportsend.SendError as e:
        console.print(f"[bold red]{escape(str(e))}[/bold red]")
        if not was_signed_in:
            reportsend.gh_forget(user)                     # a half-finished sign-in is not kept
        return False
    console.print(f"[green]Created issue #{issue['number']}.[/green] To see it, type {escape(issue['url'])} into a browser on another device, "
                  f"or run [bold]report status {issue['number']}[/bold] here to read the replies.")
    return True


def _send_discord(title, body):
    try:
        reportsend.send_discord(title, body)
    except reportsend.SendError as e:
        console.print(f"[bold red]{escape(str(e))}[/bold red]")
        return False
    console.print("[green]Sent. It reached the developer's Discord channel (it is not a GitHub issue, so there is no number to follow).[/green]")
    return True


def execute(args=None):
    args = list(args or [])
    if args[:1] == ["status"]:
        return _status(args[1:])
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
        online = not _locked_down()
        options = {"f": "(f)ile"}
        if online and reportsend.can_github():
            options["g"] = "(g)itHub issue, signing in on another device"
        if online and reportsend.can_discord():
            options["d"] = "(d)iscord, no account needed"
        if online and relay:
            options["s"] = "(s)end through the relay"
        options["n"] = "(n)o"
        pick = Prompt.ask("What would you like to do? " + ", ".join(options.values()), choices=list(options), default="f")
        if pick == "g" and not Confirm.ask("Post this report as a public issue on GitHub under your account?", default=False):
            pick = "n"
        if pick == "d" and not Confirm.ask("Send this report to the developer's Discord channel?", default=False):
            pick = "n"
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled. Nothing was sent.[/yellow]")
        return False

    stamp = time.strftime("%Y%m%d-%H%M%S")
    if waiting and pick == "n":
        console.print("[yellow]Nothing was sent. The report stays in the waiting list.[/yellow]")
        return True
    done = pick in ("f", "s")
    try:
        if pick == "f":
            path = fs.resolve(f"~/problem-report-{stamp}.txt", write=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(body)
            console.print(f"[green]Saved the report as {escape(fs.display(path, tilde=True))}.[/green]")
            # PythonOS is a command line system: it cannot open a link, so it gives a short address to type on another device
            console.print("To report it from [bold]another device[/bold] (your phone or another computer):")
            console.print(f"  1. Get the file there: run [bold]share send {escape(fs.display(path, tilde=True))}[/bold] here and type the address it shows into that device's browser")
            console.print(f"  2. Open [bold cyan]{report.ISSUE_URL}[/bold cyan] there and paste the text of the file")
        elif pick == "g":
            done = _send_github(title, body)
            if not done:
                console.print("[yellow]Nothing was posted. Try again, or choose another way (report keeps nothing until you pick).[/yellow]")
        elif pick == "d":
            done = _send_discord(title, body)
        elif pick == "s":
            if not Confirm.ask(f"Send this report to {escape(relay)}?", default=False):
                console.print("[yellow]Not sent.[/yellow]")
                return False
            console.print(f"[green]Sent. {escape(report.send_via_relay(relay, title, body))}[/green]")
        else:
            console.print("[yellow]Nothing was sent or saved.[/yellow]")
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled. Nothing was sent.[/yellow]")
        return False
    except Exception as e:
        console.print(f"[bold red]Could not send: {escape(str(e))}[/bold red]  (use the file option instead)")
        return False
    if waiting and done and pick in ("f", "g", "d", "s"):
        report.finish_pending(waiting)                 # handled: it leaves the waiting list
    return done


def _locked_down():
    try:
        from pyos import lockdown
        return lockdown.enabled()
    except Exception:                                  # noqa: BLE001
        return False
