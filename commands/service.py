from rich.console import Console
from rich.markup import escape
from rich.table import Table

import pyos
from pyos import audit, services

console = Console()
config = {
    "name": "service",
    "description": "The background services: service [list|status|start|stop|restart|enable|disable] [name].",
    "alias": ["services"],
}

HELP = """[bold]service[/bold] - what runs in the background while you are signed in

  service                    list the services and whether they run
  service status <name>      one service in detail
  service start <name>       start it now
  service stop <name>        stop it now (it starts again at the next sign-in unless it is also disabled)
  service restart <name>     stop and start it
  service disable <name>     do not start it at sign-in (stops it too)      service enable <name>   the opposite

Starting, stopping and disabling are for administrators. The battery monitor asks for your password first (it is what shuts the
system down cleanly when the battery is nearly empty). The services also show in [bold]taskman[/bold] and [bold]ps[/bold]."""

COLOUR = {"running": "green", "done": "dim", "stopped": "yellow", "disabled": "red"}


def _list():
    table = Table(header_style="bold blue")
    for column in ("Service", "State", "PID", "At sign-in", "What it does"):
        table.add_column(column)
    for row in services.rows():
        colour = COLOUR.get(row["state"], "white")
        table.add_row(f"[bold]{escape(row['name'])}[/bold]", f"[{colour}]{row['state']}[/{colour}]", str(row["pid"] or "-"),
                      "starts" if row["autostart"] else "[red]off[/red]", escape(row["description"]) + (" [dim](runs once)[/dim]" if row["oneshot"] else ""))
    console.print(table)
    console.print("[dim]service stop|start|restart|enable|disable <name>   (administrators)   -   service help[/dim]")
    return True


def _need_admin():
    if pyos.userinfo()[1] != "admin":
        console.print("[bold red]service: only an administrator can change services[/bold red]")
        return False
    return True


def _known(name):
    if name not in services.names():
        console.print(f"[bold red]service: no such service '{escape(name)}'.[/bold red] Known: {', '.join(services.names())}")
        return False
    return True


def execute(args=None):
    args = list(args or [])
    if not args or args[0] in ("list", "ls"):
        return _list()
    sub, rest = args[0].lower(), args[1:]
    if sub in ("help", "-h", "--help"):
        console.print(HELP)
        return True
    if not rest:
        console.print(f"[bold red]Usage:[/bold red] service {escape(sub)} <name>   (names: {', '.join(services.names())})")
        return False
    name = rest[0]
    if not _known(name):
        return False
    user = pyos.userinfo()[0]
    service = services.get(name)
    if sub == "status":
        row = next(r for r in services.rows() if r["name"] == name)
        console.print(f"[bold]{escape(name)}[/bold] - {escape(row['description'])}\n  state:      {row['state']}"
                      f"\n  pid:        {row['pid'] or '-'}\n  at sign-in: {'starts' if row['autostart'] else 'switched off'}"
                      f"\n  kind:       {'runs once, then finishes' if row['oneshot'] else 'keeps running'}")
        return True
    if sub not in ("start", "stop", "restart", "enable", "disable"):
        console.print(f"[bold red]service: unknown command '{escape(sub)}'[/bold red]")
        console.print(HELP)
        return False
    if not _need_admin():
        return False
    if sub in ("stop", "restart", "disable") and service.critical and services.instance(name) is not None:
        if not audit.elevate(f"{sub} the {name} service"):
            return False
    else:
        audit.record(f"{sub} service", name)
    if sub == "enable":
        services.set_disabled(name, False)
        console.print(f"[green]{escape(name)} will start at sign-in.[/green]")
        return True
    if sub == "disable":
        services.set_disabled(name, True)
        services.stop(name)
        console.print(f"[green]{escape(name)} is switched off and stopped; it will not start at sign-in.[/green]")
        return True
    ok, message = {"start": lambda: services.start(name, user), "stop": lambda: services.stop(name),
                   "restart": lambda: services.restart(name, user)}[sub]()
    console.print(f"[{'green' if ok else 'yellow'}]{escape(message)}[/{'green' if ok else 'yellow'}]")
    return ok
