from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm
from rich.table import Table

import pyos
from core import doctor

console = Console()
config = {"name": "doctor", "description": "Check the install (disk, files, accounts, packages, stale data) and offer fixes: doctor [--fix] [--yes]"}

ICON = {"ok": "[green]OK[/green]", "warn": "[yellow]WARN[/yellow]", "error": "[bold red]FAIL[/bold red]"}


def execute(args=None):
    args = list(args or [])
    if pyos.userinfo()[1] != "admin":
        console.print("[bold red]doctor: only an administrator can check the installation[/bold red]")
        return False
    findings = []
    with console.status("Checking the installation..."):
        findings = doctor.run_all()
    table = Table(header_style="bold blue", expand=True)
    table.add_column("", no_wrap=True)
    table.add_column("Area", style="cyan", no_wrap=True)
    table.add_column("Result")
    for f in findings:
        table.add_row(ICON[f.level], f.area, escape(f.message) + (f"  [dim](fixable: {escape(f.fix_text)})[/dim]" if f.fix else ""))
    console.print(table)
    fixable = [f for f in findings if f.fix]
    errors = sum(1 for f in findings if f.level == "error")
    warns = sum(1 for f in findings if f.level == "warn")
    console.print(f"[bold]{len(findings)} check(s):[/bold] {errors} problem(s), {warns} warning(s).")
    try:
        go = bool(fixable) and ("--fix" in args or "--yes" in args or Confirm.ask(f"Fix {len(fixable)} issue(s) now?", default=False))
        for f in fixable if go else []:
            if "--yes" in args or Confirm.ask(f"{f.area}: {f.fix_text}?", default=True):
                try:
                    console.print(f"[green]{f.area}: {escape(f.fix())}[/green]")
                    pyos.log.log(f"doctor fixed: {f.area}", user=pyos.userinfo()[0])
                    from pyos import audit
                    audit.record("doctor repaired", f.area)
                except Exception as e:
                    console.print(f"[red]{f.area}: could not fix ({escape(str(e))})[/red]")
    except (EOFError, KeyboardInterrupt):
        console.print("[yellow]Nothing was changed.[/yellow]")
        return errors == 0

    if not fixable and not errors and not warns:
        console.print("[green]Everything looks healthy.[/green]")
    return errors == 0
