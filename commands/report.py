import time

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

import pyos
from pyos import report, reportsend, screenlog, settings
from pyos.i18n import tr

console = Console()
config = {"name": "report", "description": "Prepare a problem report you can read first, then send it (GitHub, Discord) or save it: report [what went wrong] | report status [number]"}


def say(style, key, **values):
    """A line in the person's language. The text of a report itself stays English: it is read by the developers."""
    console.print(f"[{style}]{escape(tr(key, **values))}[/{style}]")


def _status(args):
    """report status [number]: what became of a report that was sent, from the public issue (no sign-in needed)."""
    wanted = args[0] if args else None
    if wanted is None:
        sent = reportsend.recorded()
        if not sent:
            console.print(escape(tr("No report has been sent from this PythonOS yet. Use report status <issue number> for any issue.")))
            return True
        for item in sent[-10:]:
            console.print(f"  #{item['number']}  {escape(item['title'])}  [dim]{time.strftime('%Y-%m-%d', time.localtime(item['time']))}[/dim]")
        wanted = str(sent[-1]["number"])
        say("dim", "Showing the newest, #{n}.", n=wanted)
    if not wanted.lstrip("#").isdigit():
        say("bold red", "Usage: report status [issue number]")
        return False
    try:
        info = reportsend.status_of(wanted.lstrip("#"))
    except reportsend.SendError as e:
        console.print(f"[bold red]{escape(str(e))}[/bold red]")
        return False
    console.print(f"[bold]#{wanted.lstrip('#')} {escape(info['title'])}[/bold]  - {escape(info['state'])}")
    say("dim", "To reply, type {address} into a browser on another device.", address=info["url"])
    for who, text in info["comments"]:
        console.print(Panel(escape(text.strip()[:1500]), title=escape(who), border_style="blue", expand=False))
    if not info["comments"]:
        say("dim", "No replies yet.")
    return True


def _send_github(title, body):
    """Post the report as a GitHub issue with the GitHub CLI (gh), signing the person in first if needed. True if it was created."""
    user = pyos.userinfo()[0]
    was_signed_in = False
    try:
        if not reportsend.ensure_gh(lambda question: Confirm.ask(question, default=True), console.print):
            say("yellow", "Nothing was downloaded, so nothing was posted.")
            return False
        was_signed_in = reportsend.gh_signed_in(user)
        if not was_signed_in:
            lines = [tr("This computer has no web browser, so do the sign-in on another device (your phone or another computer):"),
                     "  " + tr("1. GitHub's tool is about to show a one-time code. If it asks to open a browser, press Enter: it cannot, and carries on."),
                     "  " + tr("2. On the other device open {address}, sign in if it asks, and type the code.", address="https://github.com/login/device"),
                     "  " + tr("3. Approve it. Then come back here: the report is posted by itself."),
                     "[dim]" + escape(tr("Press Ctrl+C to stop.")) + "[/dim]"]
            console.print(Panel("\n".join(line if line.startswith("[dim]") else escape(line) for line in lines), title="[bold]" + escape(tr("Sign in to GitHub")) + "[/bold]",
                                border_style="green", expand=False))
            reportsend.gh_login(user)
        with console.status(escape(tr("Creating the issue..."))):
            issue = reportsend.gh_create_issue(user, title, body)
        stay = was_signed_in or Confirm.ask(tr("Stay signed in to GitHub on this account for next time? (gh auth logout removes it)"), default=False)
        if not stay:
            reportsend.gh_forget(user)
            say("dim", "The sign-in was deleted from this computer.")
    except reportsend.SendError as e:
        pyos.log.log(f"report: GitHub failed: {str(e)[:200]}", "WARN", user=user)
        console.print(f"[bold red]{escape(str(e))}[/bold red]")
        if not was_signed_in:
            reportsend.gh_forget(user)                     # a half-finished sign-in is not kept
        return False
    pyos.log.log(f"report: posted as GitHub issue #{issue['number']}", user=user)
    say("green", "Created issue #{n}. To see it, type {address} into a browser on another device, or run report status {n} here to read the replies.",
        n=issue["number"], address=issue["url"])
    return True


def _send_discord(title, body):
    try:
        reportsend.send_discord(title, body)
    except reportsend.SendError as e:
        pyos.log.log(f"report: Discord failed: {str(e)[:200]}", "WARN")
        console.print(f"[bold red]{escape(str(e))}[/bold red]")
        return False
    pyos.log.log("report: sent to Discord")
    say("green", "Sent. It reached the developer's Discord channel (it is not a GitHub issue, so there is no number to follow).")
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
                say("green", "No crash reports are waiting.")
                return True
            waiting = found[-1][1]
            title, body = report.read_pending(waiting)
            say("dim", "{n} waiting; this is the newest ({name}). It was written when PythonOS crashed, so it works without a network.",
                n=len(found), name=found[-1][0])
        else:
            if not text:
                text = Prompt.ask(escape(tr("What went wrong? (one or two sentences, or leave blank)")), default="")
            screen = False
            if screenlog.available() and "--no-screen" not in args:
                shown = screenlog.text(report.SCREEN_LINES).count("\n") + 1
                screen = "--screen" in args or Confirm.ask(
                    escape(tr("Share your terminal log? That is the last {n} lines of what was on your screen: the commands you typed and what PythonOS "
                              "answered. You will see it below, with the rest of the report, before anything is sent", n=shown)), default=False)
            body = report.redact(report.build(text, include_log="--no-log" not in args, include_screen=screen))
            title = text.strip().splitlines()[0][:70] if text.strip() else "Problem report"
        console.print(Panel(escape(body), title="[bold]" + escape(tr("This is everything the report contains")) + "[/bold]", border_style="blue"))
        say("dim", "Names, home folders, email and IP addresses were replaced. Nothing is sent unless you choose below.")
        relay = str(settings.get("report_relay") or "")
        online = not _locked_down()
        options = {}
        if online and reportsend.can_github():
            options["g"] = tr("(g)itHub issue, signing in on another device")
        if online and reportsend.can_discord():
            options["d"] = tr("(d)iscord, no account needed")
        if online and relay:
            options["s"] = tr("(s)end through the relay")
        if not options:
            console.print("[yellow]" + escape(tr("This copy of PythonOS has no way to send a report from here")) +
                          (escape(" " + tr("(reports are switched off in lockdown mode)")) if not online else "") + ".[/yellow]")
            if waiting:
                say("dim", "The crash report stays in the waiting list.")
            return False
        options["n"] = tr("(n)o")
        pick = Prompt.ask(escape(tr("What would you like to do?")) + " " + escape(", ".join(options.values())), choices=list(options), default="n")
        if pick == "g" and not Confirm.ask(escape(tr("Post this report as a public issue on GitHub under your account?")), default=False):
            pick = "n"
        if pick == "d" and not Confirm.ask(escape(tr("Send this report to the developer's Discord channel?")), default=False):
            pick = "n"
    except (KeyboardInterrupt, EOFError):
        console.print()
        say("yellow", "Cancelled. Nothing was sent.")
        return False

    if waiting and pick == "n":
        say("yellow", "Nothing was sent. The report stays in the waiting list.")
        return True
    done = pick == "s"
    try:
        if pick == "g":
            done = _send_github(title, body)
            if not done:
                say("yellow", "Nothing was posted. Try again, or choose another way (report keeps nothing until you pick).")
        elif pick == "d":
            done = _send_discord(title, body)
        elif pick == "s":
            if not Confirm.ask(escape(tr("Send this report to {address}?", address=relay)), default=False):
                say("yellow", "Not sent.")
                return False
            console.print("[green]" + escape(tr("Sent.")) + " " + escape(report.send_via_relay(relay, title, body)) + "[/green]")
        else:
            say("yellow", "Nothing was sent.")
    except (KeyboardInterrupt, EOFError):
        console.print()
        say("yellow", "Cancelled. Nothing was sent.")
        return False
    except Exception as e:
        console.print("[bold red]" + escape(tr("Could not send: {reason}", reason=str(e))) + "[/bold red]  " + escape(tr("(try again, or choose another way)")))
        return False
    if waiting and done and pick in ("g", "d", "s"):
        report.finish_pending(waiting)                 # handled: it leaves the waiting list
    return done


def _locked_down():
    try:
        from pyos import lockdown
        return lockdown.enabled()
    except Exception:                                  # noqa: BLE001
        return False
