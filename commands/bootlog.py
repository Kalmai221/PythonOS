import datetime

from rich.console import Console
from rich.table import Table

from core import bootlog

console = Console()
config = {"name": "bootlog", "description": "Show how the last boot went: bootlog [list | N]  (step by step, with timings)"}

COLOURS = {"ok": "green", "warn": "yellow", "fail": "red"}


def _show(boot, label):
    table = Table(title=label, header_style="bold blue")
    table.add_column("#", justify="right")
    table.add_column("Step")
    table.add_column("Result")
    table.add_column("Time", justify="right")
    table.add_column("Notes", style="dim")
    for i, s in enumerate(boot["steps"], 1):
        colour = COLOURS.get(s["status"], "white")
        table.add_row(str(i), s["name"], f"[{colour}]{s['status'].upper()}[/{colour}]", f"{s['ms']:.0f} ms", s.get("detail", ""))
    console.print(table)
    animation = boot.get("animation_ms", 0)
    console.print(f"Total [bold]{boot['total_ms'] / 1000:.2f} s[/bold]"
                  + (f"  [dim](of which {animation / 1000:.2f} s is the boot animation pause; see: settings set boot_speed instant)[/dim]" if animation else ""))


def execute(args=None):
    boots = bootlog.load()
    if not boots:
        console.print("[yellow]No boot has been recorded yet.[/yellow]")
        return True
    arg = args[0] if args else ""
    if arg == "list":
        table = Table(header_style="bold blue")
        table.add_column("#", justify="right")
        table.add_column("When")
        table.add_column("Total", justify="right")
        table.add_column("Problems")
        for i, b in enumerate(boots, 1):
            bad = [s["name"] for s in b["steps"] if s["status"] != "ok"]
            table.add_row(str(i), datetime.datetime.fromtimestamp(b["time"]).strftime("%Y-%m-%d %H:%M:%S"), f"{b['total_ms'] / 1000:.2f} s",
                          ", ".join(bad) or "-")
        console.print(table)
        console.print("[dim]Show one with: bootlog <number>[/dim]")
        return True
    index = len(boots)
    if arg.isdigit():
        index = int(arg)
        if not 1 <= index <= len(boots):
            console.print(f"[bold red]bootlog: there are {len(boots)} saved boot(s)[/bold red]")
            return False
    boot = boots[index - 1]
    _show(boot, "Boot at " + datetime.datetime.fromtimestamp(boot["time"]).strftime("%Y-%m-%d %H:%M:%S"))
    return True
