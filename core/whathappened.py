"""What happened to the previous session: shown at boot after an unexpected shutdown or a crash, and by the whathappened command."""
import os
import time

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel

import pyos
from pyos import log, session

console = Console()


def last_session_lines(limit=8):
    """The last log lines written before the current boot (so: what the previous session was doing when it stopped)."""
    try:
        entries = log.entries()
    except Exception:
        return []
    marks = [i for i, e in enumerate(entries) if "System booted" in e["message"]]
    end = marks[-1] if marks else len(entries)
    return [e["raw"] for e in entries[max(0, end - limit):end]]


def crash_reports(since):
    folder = os.path.join(pyos.fs.BASE_DIR, "var", "log")
    try:
        names = sorted(n for n in os.listdir(folder) if n.startswith("crash-") and n.endswith(".log"))
    except OSError:
        return []
    return [n for n in names if os.path.getmtime(os.path.join(folder, n)) >= (since or 0) - 5]


def describe(previous=None):
    """(headline, [detail lines]) for the previous run, or (None, []) when it ended normally."""
    previous = previous or session.previous()
    state = previous.get("state")
    started = previous.get("started")
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(started)) if started else "an unknown time"
    if state == "unexpected":
        headline = f"PythonOS was not shut down properly last time (it started at {when})."
        details = ["The power may have been cut, the window closed, or the program ended without warning.",
                   "Your files are safe: everything is written as you go."]
    elif state == "crashed":
        headline = f"PythonOS stopped with an error last time ({previous.get('code') or 'unknown error'})."
        details = ["The blue screen restarted it. The full trace was saved as a crash report."]
    else:
        return None, []
    reports = crash_reports(started)
    if reports:
        details.append("Crash report: /var/log/" + reports[-1] + "   (read it with: cat /var/log/" + reports[-1] + ")")
    lines = last_session_lines()
    if lines:
        details.append("What it was doing at the end (from the system log):")
        details.extend("  " + line for line in lines)
    details.append("Next steps: doctor (check for problems), logs --crashes, or report (prepare a problem report to send).")
    return headline, details


def show(previous=None, full=True):
    headline, details = describe(previous)
    if headline is None:
        console.print("[green]The last session ended normally.[/green]" if full else "")
        return False
    body = escape(headline) + "\n\n" + "\n".join(escape(d) for d in (details if full else details[:2]))
    console.print(Panel(body, title="[bold yellow]What happened[/bold yellow]", border_style="yellow", expand=False))
    return True
