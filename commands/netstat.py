"""netstat: the network connections of this computer."""
import psutil
from rich.console import Console
from rich.table import Table

console = Console()
config = {"name": "netstat", "description": "List network connections (netstat [-l] [-a]); -l only the listening ones.", "alias": ["ss"]}


def rows(listening_only, everything):
    found = []
    try:
        connections = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, OSError):
        return None
    for c in connections:
        state = c.status if c.type == 1 else "UDP"
        if listening_only and state not in ("LISTEN", "UDP"):
            continue
        if not everything and not listening_only and state in ("TIME_WAIT", "CLOSE_WAIT"):
            continue
        local = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "-"
        remote = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "-"
        found.append(("tcp" if c.type == 1 else "udp", local, remote, state))
    return sorted(found, key=lambda r: (r[3], r[1]))


def execute(args=None):
    args = args or []
    found = rows("-l" in args, "-a" in args)
    if found is None:
        console.print("[bold red]netstat: this system does not let PythonOS list connections (needs more rights)[/bold red]")
        return False
    table = Table(header_style="bold blue")
    for column in ("Proto", "Local address", "Remote address", "State"):
        table.add_column(column)
    for row in found:
        table.add_row(*row)
    console.print(table if found else "[yellow]No connections.[/yellow]")
    return True
