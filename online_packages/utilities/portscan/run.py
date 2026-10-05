#!/usr/bin/env python3
"""Port scanner for your own computer: shows which network ports are open on this machine (what is listening for connections), so you
can spot services you did not expect. It only scans this computer (localhost and this device's own network address) - it refuses any other
address. Usage: portscan [quick|common|all|<from>-<to>|<port>[,<port>...]]   quick = the usual suspects (default), common = 1-1024,
all = 1-65535 (slow)."""
import socket
import sys
from concurrent.futures import ThreadPoolExecutor

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table

console = Console()
KNOWN = {21: "FTP", 22: "SSH", 23: "Telnet (unsafe)", 25: "SMTP mail", 53: "DNS", 80: "HTTP web", 110: "POP3 mail", 135: "Windows RPC",
         139: "NetBIOS", 143: "IMAP mail", 443: "HTTPS web", 445: "Windows file sharing", 631: "Printing (CUPS)", 993: "IMAPS", 1433: "SQL Server",
         3000: "development server", 3306: "MySQL", 3389: "Remote Desktop", 5000: "development server", 5432: "PostgreSQL", 5900: "VNC screen sharing",
         6379: "Redis", 8000: "development server", 8080: "alternative web", 8443: "alternative HTTPS", 9000: "development server",
         27017: "MongoDB"}
QUICK = sorted(KNOWN)
RISKY = {23: "Telnet sends everything unencrypted", 21: "FTP sends passwords unencrypted", 3389: "Remote Desktop open on this machine",
         5900: "screen sharing is open", 445: "file sharing is open", 6379: "Redis is often left without a password",
         27017: "MongoDB is often left without a password"}


def own_addresses():
    """This computer's addresses: loopback and its network address. Nothing else may be scanned."""
    found = {"127.0.0.1"}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            found.add(s.getsockname()[0])
    except OSError:
        pass
    try:
        found.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    return found


def parse_ports(text):
    text = (text or "quick").strip().lower()
    if text == "quick":
        return QUICK
    if text == "common":
        return list(range(1, 1025))
    if text == "all":
        return list(range(1, 65536))
    ports = set()
    for part in text.split(","):
        if "-" in part:
            a, _, b = part.partition("-")
            if not (a.isdigit() and b.isdigit()):
                raise ValueError(f"'{part}' is not a port range like 20-80")
            ports.update(range(int(a), int(b) + 1))
        elif part.isdigit():
            ports.add(int(part))
        else:
            raise ValueError(f"'{part}' is not a port number")
    if not ports or min(ports) < 1 or max(ports) > 65535:
        raise ValueError("ports are numbers from 1 to 65535")
    return sorted(ports)


def check(args):
    address, port = args
    try:
        with socket.create_connection((address, port), timeout=0.4):
            return port
    except OSError:
        return None


def scan(address, ports):
    open_ports = []
    with Progress(TextColumn("Scanning {task.description}"), BarColumn(), TextColumn("{task.completed}/{task.total}"), console=console,
                  transient=True) as progress:
        task = progress.add_task(address, total=len(ports))
        with ThreadPoolExecutor(128) as pool:
            for result in pool.map(check, ((address, p) for p in ports)):
                progress.advance(task)
                if result:
                    open_ports.append(result)
    return sorted(open_ports)


def main(args):
    ports = parse_ports(args[0] if args else "quick")
    if len(args) > 1:
        host = args[1]
        try:
            ip = socket.gethostbyname(host)
        except OSError:
            console.print("[red]Unknown host.[/red]")
            return
        if ip not in own_addresses():
            console.print("[bold red]This tool only scans your own computer. Scanning other machines without permission is not allowed.[/bold red]")
            return
    addresses = ["127.0.0.1"]
    others = sorted(own_addresses() - {"127.0.0.1"})
    if others:
        addresses.append(others[0])
    for address in addresses:
        found = scan(address, ports)
        title = f"{address} ({'this computer only' if address.startswith('127.') else 'reachable from your network'})"
        if not found:
            console.print(f"[green]{title}: no open ports among the {len(ports)} checked.[/green]")
            continue
        table = Table(title=title, header_style="bold blue")
        for col in ("Port", "Usually", "Note"):
            table.add_column(col)
        for p in found:
            table.add_row(str(p), KNOWN.get(p, ""), f"[yellow]{RISKY[p]}[/yellow]" if p in RISKY and not address.startswith("127.") else "")
        console.print(table)
    console.print("[dim]An open port means a program is listening there. Ports open on 127.0.0.1 only are not reachable from other devices.[/dim]")


def execute(args=None):
    try:
        main(list(args or []))
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
