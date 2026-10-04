import re
from collections import deque
from rich.console import Console
from rich.markup import escape
from rich.table import Table
import pyos
from pyos.log import LOG_FILE

console = Console()
config = {"name": "last", "description": "Recent logins and failed attempts: last [N] [-f]. Admins see everyone, others only themselves."}

LINE = re.compile(r"^(\S+ \S+) \[(\w+)\] (\S+?): (.*)$")
INTERESTING = ("login ok", "login failed", "logout", "session locked", "session unlocked", "su to", "password changed")


def execute(args=None):
    args = list(args or [])
    failed_only = "-f" in args
    count = next((int(a) for a in args if a.isdigit()), 15)
    user, role = pyos.userinfo()
    if not user:
        console.print("[bold red]last: you are not logged in.[/bold red]")
        return False
    try:
        with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
            lines = deque(f, maxlen=5000)
    except OSError:
        console.print("[dim]The log is empty.[/dim]")
        return True

    rows = []
    for raw in lines:
        m = LINE.match(raw.strip())
        if not m:
            continue
        when, level, who, text = m.groups()
        if not text.startswith(INTERESTING):
            continue
        if role != "admin" and who != user:
            continue
        if failed_only and not text.startswith("login failed"):
            continue
        rows.append((when, who, text, level))
    if not rows:
        console.print("[dim]Nothing to show.[/dim]")
        return True
    table = Table(header_style="bold blue")
    for col in ("When", "User", "Event"):
        table.add_column(col)
    for when, who, text, level in rows[-count:]:
        style = "red" if "failed" in text else "yellow" if level == "WARN" else "white"
        table.add_row(when, escape(who), f"[{style}]{escape(text)}[/{style}]")
    console.print(table)
    return True
