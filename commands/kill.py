from rich.console import Console
import pyos
from pyos import jobs, scheduler

console = Console()
config = {"name": "kill", "description": "Stop a task or background job (kill <pid or job number>). Jobs stop when they next check, e.g. during sleep."}


def execute(args=None):
    if not args or not args[0].isdigit():
        console.print("[bold red]Usage:[/bold red] kill <job number>   (see: jobs)")
        return False
    user, role = pyos.userinfo()[0], pyos.userinfo()[1]
    number = int(args[0])
    if any(r["pid"] == number for r in pyos.tasks.listing(user)):          # a task's PID (see ps, taskman)
        ok, message = pyos.tasks.stop(number, user, admin=(role == "admin"))
        colour = "green" if ok else "yellow"
        console.print(f"[{colour}]{message}[/{colour}]")
        return ok
    job = jobs.get(number)
    if job is None or (job.user not in (None, user)):
        console.print(f"[bold red]kill: no such job: {args[0]}[/bold red]")
        return False
    if not jobs.cancel(job.id):
        console.print(f"[yellow]Job {job.id} is already {job.status}.[/yellow]")
        return False
    console.print(f"[green]Asked job {job.id} to stop.[/green] [dim](A command that never checks keeps running until it finishes.)[/dim]")
    return True
