import time
from rich.console import Console
import pyos
from pyos import jobs

console = Console()
config = {"name": "fg", "description": "Show a background job's output, waiting for it if needed (fg <job number>)."}


def execute(args=None):
    user = pyos.userinfo()[0]
    mine = jobs.all_jobs(user)
    if args and args[0].isdigit():
        job = jobs.get(int(args[0]))
    else:
        job = mine[-1] if mine else None          # no number: the most recent job
    if job is None or job not in mine:
        console.print("[bold red]fg: no such job (see: jobs)[/bold red]")
        return False

    try:
        if job.status == "running":
            console.print(f"[dim][{job.id}] {job.command} - waiting (Ctrl+C leaves it running)[/dim]")
            while job.status == "running":
                time.sleep(0.2)
    except KeyboardInterrupt:
        console.print("\n[yellow]Left running in the background.[/yellow]")
        return True
    if job.output:
        console.print(job.output, markup=False, highlight=False, end="" if job.output.endswith("\n") else "\n")
    console.print(f"[dim][{job.id}] {job.status}[/dim]")
    return job.status == "done"
