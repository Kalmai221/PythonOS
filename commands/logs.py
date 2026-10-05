import datetime
import os
from collections import Counter

from rich.console import Console
from rich.markup import escape
from rich.table import Table

import pyos
import pyos.fs as fs
from pyos import log

console = Console()
config = {"name": "logs", "description": "Show and search the system log: logs [N] [--user U] [--level L] [--since T] [--grep W] [--export FILE]",
          "alias": ["dmesg"]}

HELP = """[bold]logs[/bold] - the system log (logins, account changes, crashes, updates)

  logs                          the last 20 lines
  logs 100                      the last 100 lines
  logs --user bob               only what bob did or what happened to bob's account
  logs --level warn             warnings and errors only (info, warn, error)
  logs --since yesterday        from a time on: today, yesterday, 2h, 3d, 2026-10-05, '2026-10-05 14:30'
  logs --until 2026-10-06       up to a time
  logs --grep login             lines containing a word
  logs --summary                counts by level and by user, and the last failed logins
  logs --crashes                list saved crash reports (open one with cat)
  logs --export ~/log.txt       write the matching lines to a file (add --csv for a spreadsheet file)

Administrators see everything; other users see their own lines and system lines."""


def _take(args, flag):
    """Remove `flag value` from args; returns the value or None. Raises ValueError if the value is missing."""
    if flag not in args:
        return None
    i = args.index(flag)
    if i + 1 >= len(args):
        raise ValueError(f"{flag} needs a value")
    value = args[i + 1]
    del args[i:i + 2]
    return value


def _show(lines):
    for e in lines:
        style = "red" if e["level"] == "ERROR" else "yellow" if e["level"] in ("WARN", "WARNING") else None
        console.print(e["raw"], markup=False, highlight=False, style=style)


def _summary(items):
    levels = Counter(e["level"] for e in items)
    users = Counter(e["user"] or "(system)" for e in items)
    table = Table(title="Log summary", header_style="bold blue")
    table.add_column("Level")
    table.add_column("Lines", justify="right")
    for level, n in sorted(levels.items(), key=lambda kv: -log.LEVELS.get(kv[0].lower(), 1)):
        table.add_row(level, str(n))
    console.print(table)
    table = Table(header_style="bold blue")
    table.add_column("User")
    table.add_column("Lines", justify="right")
    for user, n in users.most_common(10):
        table.add_row(escape(user), str(n))
    console.print(table)
    failed = [e for e in items if "fail" in e["message"].lower() or "locked" in e["message"].lower() or "wrong" in e["message"].lower()]
    if failed:
        console.print("[bold]Recent failed logins and lockouts[/bold]")
        _show(failed[-5:])
    if items:
        console.print(f"[dim]{items[0]['time']:%Y-%m-%d %H:%M} to {items[-1]['time']:%Y-%m-%d %H:%M}[/dim]")


def _crashes():
    folder = os.path.join(fs.BASE_DIR, "var", "log")
    try:
        names = sorted(n for n in os.listdir(folder) if n.startswith("crash-") and n.endswith(".log"))
    except OSError:
        names = []
    if not names:
        console.print("[green]No crash reports saved.[/green]")
        return
    for n in names[-10:]:
        console.print(f"/var/log/{n}")
    console.print("[dim]Read one with: cat /var/log/<name>[/dim]")


def execute(args=None):
    args = list(args or [])
    if args and args[0] in ("help", "-h", "--help"):
        console.print(HELP)
        return True
    me, role = pyos.userinfo()
    try:
        who = _take(args, "--user")
        level = _take(args, "--level")
        since_text, until_text = _take(args, "--since"), _take(args, "--until")
        grep = _take(args, "--grep")
        export = _take(args, "--export")
        since = log.parse_when(since_text) if since_text else None
        until = log.parse_when(until_text) if until_text else None
        if level and level.lower() not in log.LEVELS:
            raise ValueError("--level must be info, warn or error")
    except ValueError as e:
        console.print(f"[bold red]logs: {escape(str(e))}[/bold red]")
        return False
    csv = "--csv" in args
    summary = "--summary" in args
    crashes = "--crashes" in args
    args = [a for a in args if a not in ("--csv", "--summary", "--crashes")]
    count = int(args[0]) if args and args[0].isdigit() else None

    if crashes:
        if role != "admin":
            console.print("[bold red]logs: crash reports are for administrators[/bold red]")
            return False
        _crashes()
        return True

    if not os.path.exists(log.LOG_FILE):
        console.print("[bold yellow]The system log is empty.[/bold yellow]")
        return True
    items = log.query(log.entries(), user=who, level=level, since=since, until=until, text=grep,
                      only_user=None if role == "admin" else me)
    if summary:
        _summary(items)
        return True
    filtered = any([who, level, since, until, grep, export])
    shown = items[-(count or (100000 if export else (200 if filtered else 20))):]
    if export:
        try:
            path = fs.resolve(export, write=True)
            with open(path, "w", encoding="utf-8", newline="") as f:
                if csv:
                    f.write("time,level,user,message\n")
                    for e in shown:
                        msg = e["message"].replace('"', '""')
                        f.write(f'{e["time"]:%Y-%m-%d %H:%M:%S},{e["level"]},{e["user"]},"{msg}"\n')
                else:
                    f.writelines(e["raw"] + "\n" for e in shown)
        except (OSError, PermissionError) as e:
            console.print(f"[bold red]logs: {escape(fs.errtext(e))}[/bold red]")
            return False
        console.print(f"Wrote {len(shown)} line(s) to {escape(export)}.")
        return True
    if not shown:
        console.print("[yellow]No log lines match.[/yellow]")
        return True
    _show(shown)
    return True
