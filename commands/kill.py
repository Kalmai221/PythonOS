from rich.console import Console
import pyos
from pyos import jobs, scheduler

console = Console()
config = {"name": "kill", "description": "Stop a background job (kill <job number>). Jobs stop when they next check, e.g. during sleep."}


def execute(args=None):
    if not args or not args[0].isdigit():
        console.print("[bold red]Usage:[/bold red] kill <job number>   (see: jobs)")
        return False
    user = pyos.userinfo()[0]
    job = jobs.get(int(args[0]))
    if job is None or (job.user not in (None, user)):
        console.print(f"[bold red]kill: no such job: {args[0]}[/bold red]")
        return False
    if not jobs.cancel(job.id):
        console.print(f"[yellow]Job {job.id} is already {job.status}.[/yellow]")
        return False
    console.print(f"[green]Asked job {job.id} to stop.[/green] [dim](A command that never checks keeps running until it finishes.)[/dim]")
    return True
