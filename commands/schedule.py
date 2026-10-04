from rich.console import Console
from rich.markup import escape
from rich.table import Table
import datetime
import pyos
from pyos import scheduler

console = Console()
config = {
    "name": "schedule",
    "description": "Run commands later: schedule add <in|at|every|daily> <when> <command> | list | remove <id> | run <id>",
    "alias": ["cron"],
}

HELP = """[bold]schedule[/bold] - run commands later or repeatedly

  schedule add in 10m backup create          once, in 10 minutes   (s, m, h, d)
  schedule add at 14:30 echo lunch           once, at 14:30
  schedule add every 5m ls                   every 5 minutes
  schedule add daily 08:00 date              every day at 08:00
  schedule list                              your scheduled tasks
  schedule remove 2                          delete task 2
  schedule run 2                             run task 2 right now

Output arrives as a notification. Tasks run while you are logged in and must not ask questions."""


def execute(args=None):
    args = list(args or [])
    user = pyos.userinfo()[0]
    if not args or args[0] in ("help", "-h", "--help"):
        console.print(HELP)
        return True
    sub, rest = args[0].lower(), args[1:]

    if sub == "add":
        try:
            task = scheduler.add(user, rest)
        except ValueError as e:
            console.print(f"[bold red]schedule: {escape(str(e))}[/bold red]")
            return False
        console.print(f"[green]Scheduled #{task['id']}:[/green] {escape(task['command'])} [dim]({scheduler.describe(task)})[/dim]")
        return True

    if sub in ("list", "ls"):
        tasks = scheduler.tasks_for(user)
        if not tasks:
            console.print("[dim]Nothing scheduled. Try: schedule add every 1h date[/dim]")
            return True
        table = Table(header_style="bold blue")
        for col in ("#", "When", "Next run", "Command", "Last"):
            table.add_column(col)
        for t in tasks:
            last = "-" if t["last_run"] is None else ("ok" if not t["last_status"] else "failed")
            table.add_row(str(t["id"]), scheduler.describe(t),
                          datetime.datetime.fromtimestamp(t["next_run"]).strftime("%a %H:%M:%S"), escape(t["command"]), last)
        console.print(table)
        return True

    if sub in ("remove", "rm", "delete"):
        if not rest or not rest[0].isdigit():
            console.print("[bold red]Usage:[/bold red] schedule remove <id>")
            return False
        if scheduler.remove(user, int(rest[0]), admin=pyos.userinfo()[1] == "admin"):
            console.print(f"[green]Removed task {rest[0]}.[/green]")
            return True
        console.print(f"[bold red]schedule: no task {rest[0]}[/bold red]")
        return False

    if sub == "run":
        if not rest or not rest[0].isdigit():
            console.print("[bold red]Usage:[/bold red] schedule run <id>")
            return False
        task = next((t for t in scheduler.tasks_for(user) if t["id"] == int(rest[0])), None)
        if task is None:
            console.print(f"[bold red]schedule: no task {rest[0]}[/bold red]")
            return False
        import shell
        status, output = shell.run_captured(task["command"])
        console.print(output, markup=False, highlight=False, end="")
        return status == 0

    console.print(f"[bold red]schedule: unknown subcommand '{escape(sub)}'[/bold red]")
    console.print(HELP)
    return False
