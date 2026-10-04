from rich.console import Console
from rich.markup import escape
from rich.table import Table
import pyos
from pyos import jobs

console = Console()
config = {"name": "jobs", "description": "List background jobs started with & (jobs [clear]). See also: fg, kill."}


def _format_time(seconds):
    return f"{int(seconds // 60)}m{int(seconds % 60):02d}s" if seconds >= 60 else f"{seconds:.1f}s"


def execute(args=None):
    user = pyos.userinfo()[0]
    if args and args[0] == "clear":
        jobs.forget_finished(user)
        return True
    mine = jobs.all_jobs(user)
    if not mine:
        console.print("[dim]No background jobs. Start one by ending a command with &, for example: sleep 10 &[/dim]")
        return True
    table = Table(header_style="bold blue")
    table.add_column("#", justify="right")
    table.add_column("State")
    table.add_column("Time", justify="right")
    table.add_column("Command")
    colours = {"running": "yellow", "done": "green", "failed": "red", "cancelled": "dim"}
    for job in mine:
        c = colours.get(job.status, "white")
        table.add_row(str(job.id), f"[{c}]{job.status}[/{c}]", _format_time(job.elapsed()), escape(job.command))
    console.print(table)
    return True
