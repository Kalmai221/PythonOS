import json
import time

from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm
from rich.table import Table

import pyos
from core import doctor

console = Console()
config = {"name": "doctor", "description": "Check the install (disk, files, accounts, packages, network...) and offer fixes: doctor [--fix] [--online] [--problems]"}

ICON = {"ok": "[green]OK[/green]", "warn": "[yellow]WARN[/yellow]", "error": "[bold red]FAIL[/bold red]"}
USAGE = ("usage: doctor [--fix] [--yes] [--online] [--problems] [--only name,...] [--json] [--timings] [--list]\n"
         "  --fix       offer the fixes without asking first    --yes   apply every fix without asking\n"
         "  --online    also check the internet and the latest release\n"
         "  --problems  show only what needs attention           --only  run just those checks (see --list)\n"
         "  --json      machine-readable result                  --timings  how long each check took")


def _grade(points):
    if points >= 95:
        return "[green]healthy[/green]"
    if points >= 75:
        return "[yellow]needs a little attention[/yellow]"
    return "[bold red]needs attention[/bold red]"


def _compare(findings, before):
    """What changed since the last run: new problems and problems that went away."""
    if not before:
        return
    old = {(a, m) for _lvl, a, m in before.get("findings", [])}
    now = {(f.area, f.message) for f in findings if f.level != "ok"}
    gone, new = old - now, now - old
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(before.get("time", 0)))
    if gone or new:
        console.print(f"[dim]Since the last check ({when}): {len(gone)} resolved, {len(new)} new.[/dim]")
        for area, message in sorted(new):
            console.print(f"  [yellow]new[/yellow]  {escape(area)}: {escape(message)}")
        for area, _message in sorted(gone):
            console.print(f"  [green]fixed[/green] {escape(area)}")
    else:
        console.print(f"[dim]Nothing has changed since the last check ({when}).[/dim]")


def execute(args=None):
    args = list(args or [])
    if "-h" in args or "--help" in args:
        console.print(escape(USAGE))
        return True
    if "--list" in args:
        console.print("Checks: " + ", ".join(doctor.names()) + "\n[dim](network needs --online)[/dim]")
        return True
    if pyos.userinfo()[1] != "admin":
        console.print("[bold red]doctor: only an administrator can check the installation[/bold red]")
        return False
    only = None
    if "--only" in args:
        at = args.index("--only")
        if at + 1 >= len(args):
            console.print("[red]doctor: --only needs a list of checks (see doctor --list)[/red]")
            return False
        only = {n.strip().lower() for n in args[at + 1].split(",") if n.strip()}
        unknown = only - set(doctor.names())
        if unknown:
            console.print(f"[red]doctor: no such check: {escape(', '.join(sorted(unknown)))} (see doctor --list)[/red]")
            return False
    online = "--online" in args or bool(only and "network" in only)
    as_json = "--json" in args
    problems_only = "--problems" in args
    timings = {}
    before = doctor.last_report()
    if as_json:
        findings = doctor.run_all(only, online, timings)
    else:
        with console.status("Checking the installation..." + (" (and the network)" if online else "")):
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
    table.add_column("Area", style="cyan", no_wrap=True)
    table.add_column("Result")
    for f in shown:
        note = ""
        if f.fix:
            note = f"\n[dim]fix: {escape(f.fix_text)}[/dim]"
        elif f.hint and f.level != "ok":
            note = f"\n[dim]what to do: {escape(f.hint)}[/dim]"
        table.add_row(ICON[f.level], f.area, escape(f.message) + note)
    if shown:
        console.print(table)
    console.print(f"[bold]{len(findings)} check(s):[/bold] {errors} problem(s), {warns} warning(s).  "
                  f"[bold]Health {points}/100[/bold], {_grade(points)}.")
    if "--timings" in args:
        slow = sorted(timings.items(), key=lambda kv: -kv[1])
        console.print("[dim]Time: " + ", ".join(f"{k} {v * 1000:.0f} ms" for k, v in slow[:8]) + "[/dim]")
    if not only:
        _compare(findings, before)

    fixable = [f for f in findings if f.fix]
    try:
        go = bool(fixable) and ("--fix" in args or "--yes" in args or Confirm.ask(f"Fix {len(fixable)} issue(s) now?", default=False))
        fixed = 0
        for f in fixable if go else []:
            if "--yes" in args or Confirm.ask(f"{f.area}: {f.fix_text}?", default=True):
                try:
                    console.print(f"[green]{f.area}: {escape(f.fix())}[/green]")
                    pyos.log.log(f"doctor fixed: {f.area}", user=pyos.userinfo()[0])
                    from pyos import audit
                    audit.record("doctor repaired", f.area)
                    fixed += 1
                except Exception as e:
                    console.print(f"[red]{f.area}: could not fix ({escape(str(e))})[/red]")
        if fixed:                                          # check again so the result is what is true now, not what was hoped
            again = doctor.run_all(only, online)
            left = sum(1 for f in again if f.level != "ok")
            console.print(f"[bold]Checked again:[/bold] {left} item(s) still need attention, health {doctor.score(again)}/100.")
            if not only:
                doctor.save_report(again)
            errors = sum(1 for f in again if f.level == "error")
            findings = again
    except (EOFError, KeyboardInterrupt):
        console.print("[yellow]Nothing was changed.[/yellow]")
        return errors == 0

    if all(f.level == "ok" for f in findings):
        console.print("[green]Everything looks healthy.[/green]")
    elif not fixable:
        console.print("[dim]Nothing here can be fixed automatically; the lines above say what to do.[/dim]")
    return errors == 0
