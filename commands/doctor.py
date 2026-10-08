import json
import time

from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm
from rich.table import Table

import pyos
from core import doctor
from pyos.i18n import tr

console = Console()
config = {"name": "doctor", "description": "Check the install (disk, files, accounts, packages, network...) and offer fixes: doctor [--fix] [--online] [--problems]"}

USAGE = ("usage: doctor [--fix] [--yes] [--online] [--problems] [--only name,...] [--json] [--timings] [--list]\n"
         "  --fix       offer the fixes without asking first    --yes   apply every fix without asking\n"
         "  --online    also check the internet and the latest release\n"
         "  --problems  show only what needs attention           --only  run just those checks (see --list)\n"
         "  --json      machine-readable result                  --timings  how long each check took")


def say(style, key, **values):
    console.print(f"[{style}]{escape(tr(key, **values))}[/{style}]")


def _icon(level):
    return {"ok": "[green]" + escape(tr("OK")) + "[/green]", "warn": "[yellow]" + escape(tr("WARN")) + "[/yellow]",
            "error": "[bold red]" + escape(tr("FAIL")) + "[/bold red]"}[level]


def _grade(points):
    if points >= 95:
        return "[green]" + escape(tr("healthy")) + "[/green]"
    if points >= 75:
        return "[yellow]" + escape(tr("needs a little attention")) + "[/yellow]"
    return "[bold red]" + escape(tr("needs attention")) + "[/bold red]"


def _compare(findings, before):
    """What changed since the last run: new problems and problems that went away."""
    if not before:
        return
    old = {(a, m) for _lvl, a, m in before.get("findings", [])}
    now = {(f.area, f.message) for f in findings if f.level != "ok"}
    gone, new = old - now, now - old
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(before.get("time", 0)))
    if gone or new:
        say("dim", "Since the last check ({when}): {gone} resolved, {new} new.", when=when, gone=len(gone), new=len(new))
        for area, message in sorted(new):
            console.print(f"  [yellow]{escape(tr('new'))}[/yellow]  {escape(area)}: {escape(message)}")
        for area, _message in sorted(gone):
            console.print(f"  [green]{escape(tr('fixed'))}[/green] {escape(area)}")
    else:
        say("dim", "Nothing has changed since the last check ({when}).", when=when)


def execute(args=None):
    args = list(args or [])
    if "-h" in args or "--help" in args:
        console.print(escape(tr(USAGE)))
        return True
    if "--list" in args:
        console.print(escape(tr("Checks:")) + " " + ", ".join(doctor.names()) + "\n[dim]" + escape(tr("(network needs --online)")) + "[/dim]")
        return True
    if pyos.userinfo()[1] != "admin":
        from pyos.userinfo import diagnose
        say("bold red", "doctor: only an administrator can check the installation")
        say("dim", "Why: {reason}. A standard user can run: sudo doctor", reason=diagnose())
        return False
    only = None
    if "--only" in args:
        at = args.index("--only")
        if at + 1 >= len(args):
            say("red", "doctor: --only needs a list of checks (see doctor --list)")
            return False
        only = {n.strip().lower() for n in args[at + 1].split(",") if n.strip()}
        unknown = only - set(doctor.names())
        if unknown:
            say("red", "doctor: no such check: {names} (see doctor --list)", names=", ".join(sorted(unknown)))
            return False
    online = "--online" in args or bool(only and "network" in only)
    as_json = "--json" in args
    problems_only = "--problems" in args
    timings = {}
    before = doctor.last_report()
    if as_json:
        findings = doctor.run_all(only, online, timings)
    else:
        with console.status(escape(tr("Checking the installation...") + (" " + tr("(and the network)") if online else ""))):
            findings = doctor.run_all(only, online, timings)
    errors = sum(1 for f in findings if f.level == "error")
    warns = sum(1 for f in findings if f.level == "warn")
    points = doctor.score(findings)
    if not only:
        doctor.save_report(findings)

    if as_json:
        print(json.dumps({"score": points, "problems": errors, "warnings": warns, "timings": {k: round(v, 3) for k, v in timings.items()},
                          "findings": [{"level": f.level, "area": f.area, "message": f.message, "check": f.check, "fixable": bool(f.fix),
                                        "hint": f.hint} for f in findings]}, indent=2))
        return errors == 0

    shown = [f for f in findings if f.level != "ok"] if problems_only else findings
    table = Table(header_style="bold blue", expand=True)
    table.add_column("", no_wrap=True)
    table.add_column(tr("Area"), style="cyan", no_wrap=True)
    table.add_column(tr("Result"))
    for f in shown:
        note = ""
        if f.fix:
            note = "\n[dim]" + escape(tr("fix: {what}", what=f.fix_text)) + "[/dim]"
        elif f.hint and f.level != "ok":
            note = "\n[dim]" + escape(tr("what to do: {what}", what=f.hint)) + "[/dim]"
        table.add_row(_icon(f.level), escape(tr(f.area)), escape(f.message) + note)
    if shown:
        console.print(table)
    console.print("[bold]" + escape(tr("{n} check(s):", n=len(findings))) + "[/bold] " +
                  escape(tr("{problems} problem(s), {warnings} warning(s).", problems=errors, warnings=warns)) + "  [bold]" +
                  escape(tr("Health {points}/100", points=points)) + "[/bold], " + _grade(points) + ".")
    if "--timings" in args:
        slow = sorted(timings.items(), key=lambda kv: -kv[1])
        console.print("[dim]" + escape(tr("Time:")) + " " + ", ".join(f"{k} {v * 1000:.0f} ms" for k, v in slow[:8]) + "[/dim]")
    if not only:
        _compare(findings, before)

    fixable = [f for f in findings if f.fix]
    try:
        go = bool(fixable) and ("--fix" in args or "--yes" in args or Confirm.ask(escape(tr("Fix {n} issue(s) now?", n=len(fixable))), default=False))
        fixed = 0
        for f in fixable if go else []:
            if "--yes" in args or Confirm.ask(escape(f"{tr(f.area)}: {f.fix_text}?"), default=True):
                try:
                    console.print(f"[green]{escape(tr(f.area))}: {escape(f.fix())}[/green]")
                    pyos.log.log(f"doctor fixed: {f.area}", user=pyos.userinfo()[0])
                    from pyos import audit
                    audit.record("doctor repaired", f.area)
                    fixed += 1
                except Exception as e:
                    say("red", "{area}: could not fix ({reason})", area=tr(f.area), reason=str(e))
        if fixed:                                          # check again so the result is what is true now, not what was hoped
            again = doctor.run_all(only, online)
            left = sum(1 for f in again if f.level != "ok")
            console.print("[bold]" + escape(tr("Checked again:")) + "[/bold] " + escape(tr("{n} item(s) still need attention, health {points}/100.",
                                                                                              n=left, points=doctor.score(again))))
            if not only:
                doctor.save_report(again)
            errors = sum(1 for f in again if f.level == "error")
            findings = again
    except (EOFError, KeyboardInterrupt):
        say("yellow", "Nothing was changed.")
        return errors == 0

    if all(f.level == "ok" for f in findings):
        say("green", "Everything looks healthy.")
    elif not fixable:
        say("dim", "Nothing here can be fixed automatically; the lines above say what to do.")
    return errors == 0
