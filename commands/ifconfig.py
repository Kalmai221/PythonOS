"""ifconfig: the network interfaces of this computer."""
import socket

import psutil
from rich.console import Console
from rich.table import Table

console = Console()
config = {"name": "ifconfig", "description": "Show the network interfaces and their addresses (ifconfig [name]).", "alias": ["ipconfig"]}


def collect():
    stats = psutil.net_if_stats()
    out = []
    for name, addresses in psutil.net_if_addrs().items():
        v4 = [a.address for a in addresses if a.family == socket.AF_INET]
        v6 = [a.address.split("%")[0] for a in addresses if a.family == socket.AF_INET6]
        mac = next((a.address for a in addresses if a.family == psutil.AF_LINK), "")
        info = stats.get(name)
        out.append({"name": name, "up": bool(info and info.isup), "speed": info.speed if info else 0, "v4": v4, "v6": v6, "mac": mac})
    return sorted(out, key=lambda i: (not i["up"], i["name"]))


def execute(args=None):
    wanted = (args or [None])[0]
    interfaces = [i for i in collect() if not wanted or i["name"] == wanted]
    if not interfaces:
        console.print(f"[bold red]ifconfig: no interface called {wanted}[/bold red]")
        return False
    table = Table(header_style="bold blue")
    for column in ("Interface", "State", "IPv4", "IPv6", "MAC", "Speed"):
        table.add_column(column)
    for i in interfaces:
        table.add_row(i["name"], "[green]up[/green]" if i["up"] else "[dim]down[/dim]", ", ".join(i["v4"]) or "-", ", ".join(i["v6"][:2]) or "-", i["mac"] or "-",
                      f"{i['speed']} Mb/s" if i["speed"] else "-")
    console.print(table)
    return True
