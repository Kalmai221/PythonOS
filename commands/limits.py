import json
import os

from rich.console import Console
from rich.markup import escape
from rich.table import Table

import pyos
from pyos import audit, limits, resources, settings

console = Console()
config = {
    "name": "limits",
    "description": "How much memory and processor time each app may use: limits [set|reset|default] ...",
}

HELP = """[bold]limits[/bold] - hold each app to a share of the computer

  limits                                   every installed app and its limits
  limits set <app> memory <MB|off>         the most memory the app may use
  limits set <app> cpu <seconds|off>       the most processor time it may use (not the time it is open)
  limits reset <app> [memory|cpu]          back to what the app declares, or the system default
  limits default <percent|off>             the default for apps: a share of PythonOS's memory (now [bold]{share}%[/bold])

An app that goes over its limit is stopped, with a message saying which limit it hit. Setting limits is for administrators.
[dim]<app> is its name, its command or its id (for example sysmon, or utilities/sysmon).[/dim]"""


def installed():
    """[(id, name, command, meta)] for the apps under files/installed_*/."""
    found = []
    base = "files"
    if not os.path.isdir(base):
        return found
    for entry in sorted(os.listdir(base)):
        if not entry.startswith("installed_"):
            continue
        category = entry[len("installed_"):]
        folder = os.path.join(base, entry)
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name, "data.json")
            try:
                with open(path, encoding="utf-8") as f:
                    meta = json.load(f)
            except (OSError, ValueError):
                continue
            found.append((f"{category}/{name}", meta.get("name", name), meta.get("command", ""), meta))
    return found


def find(text):
    text = text.lower()
    for pid, name, command, meta in installed():
        if text in (pid.lower(), pid.split("/")[-1].lower(), name.lower(), command.lower()):
            return pid, name, meta
    return None


def _mb(value):
    return "no limit" if not value else f"{value} MB"


def _sec(value):
    return "no limit" if not value else f"{value} s"


def _where(source):
    return {"you": "you set it", "app": "the app asks", "default": "system default"}[source]


def _list():
    apps = installed()
    if not apps:
        console.print("[dim]No apps are installed (see: market). Apps are held to a limit when they run.[/dim]")
        console.print(f"System default: {_mb(limits.default_memory_mb())} of memory per app.")
        return True
    table = Table(header_style="bold blue")
    for column in ("App", "Memory", "Processor time", "Where it comes from"):
        table.add_column(column)
    for pid, name, command, meta in apps:
        held = limits.for_package(pid, meta)
        table.add_row(f"[bold]{escape(name)}[/bold] [dim]{escape(command or pid)}[/dim]", _mb(held["memory_mb"]), _sec(held["cpu_seconds"]),
                      f"memory: {_where(held['source']['memory'])}" + (f"; cpu: {_where(held['source']['cpu'])}" if held["cpu_seconds"] else ""))
    console.print(table)
    total, _used, _free, _pct = resources.snapshot()
    console.print(f"[dim]System default: {_mb(limits.default_memory_mb())} per app (PythonOS owns {total // resources.MB} MB). "
                  "limits help[/dim]")
    return True


def _number(text):
    if text.lower() in ("off", "none", "no", "unlimited"):
        return 0
    if text.isdigit():
        return int(text)
    raise ValueError("give a whole number, or 'off'")


def execute(args=None):
    args = list(args or [])
    if not args:
        return _list()
    sub, rest = args[0].lower(), args[1:]
    if sub in ("help", "-h", "--help"):
        console.print(HELP.format(share=settings.get("app_memory_percent")))
        return True
    if sub == "show" and rest:
        return _list()
    if sub in ("set", "reset", "default"):
        if pyos.userinfo()[1] != "admin":
            console.print("[bold red]limits: only an administrator can change limits[/bold red]")
            return False
    if sub == "default":
        if not rest:
            console.print(f"Apps may use {settings.get('app_memory_percent')}% of PythonOS's memory by default ({_mb(limits.default_memory_mb())}).")
            return True
        try:
            value = _number(rest[0].rstrip("%"))
            if value > 100:
                raise ValueError("a percentage is 0 to 100")
            audit.record("changed the default app memory limit", f"{value}%")
            settings.set("app_memory_percent", value)
        except ValueError as e:
            console.print(f"[bold red]limits: {escape(str(e))}[/bold red]")
            return False
        console.print(f"[green]Apps may now use {value}% of PythonOS's memory by default ({_mb(limits.default_memory_mb())}).[/green]")
        return True
    if sub == "set" and len(rest) == 3:
        found = find(rest[0])
        if not found:
            console.print(f"[bold red]limits: no installed app '{escape(rest[0])}'[/bold red]")
            return False
        try:
            limits.set_limit(found[0], rest[1].lower(), _number(rest[2]))
        except ValueError as e:
            console.print(f"[bold red]limits: {escape(str(e))}[/bold red]")
            return False
        audit.record("set an app limit", f"{found[0]} {rest[1]} {rest[2]}")
        console.print(f"[green]{escape(found[1])}: {rest[1].lower()} limit is now {rest[2]}.[/green] It applies the next time the app starts.")
        return True
    if sub == "reset" and rest:
        found = find(rest[0])
        if not found:
            console.print(f"[bold red]limits: no installed app '{escape(rest[0])}'[/bold red]")
            return False
        kind = rest[1].lower() if len(rest) > 1 else None
        if kind not in (None, "memory", "cpu"):
            console.print("[bold red]limits: reset memory or cpu (or both, by leaving it out)[/bold red]")
            return False
        limits.reset(found[0], kind)
        audit.record("reset an app limit", f"{found[0]} {kind or 'all'}")
        console.print(f"[green]{escape(found[1])} is back to its default limit.[/green]")
        return True
    console.print(HELP.format(share=settings.get("app_memory_percent")))
    return False
