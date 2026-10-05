#!/usr/bin/env python3
"""LAN scanner: finds the devices on your own local network (home or office) by trying to connect to a few common ports on every address,
then lists what answered with its name and, on Linux, its hardware address. It only scans private network ranges (192.168.x.x, 10.x.x.x,
172.16-31.x.x) - never the internet. Only scan networks you own or are allowed to examine.
Usage: lanscan  |  lanscan <192.168.1.0/24>"""
import ipaddress
import socket
import sys
from concurrent.futures import ThreadPoolExecutor

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table

console = Console()
PORTS = [80, 443, 22, 445, 139, 135, 53, 8080, 62078, 5353, 1900]      # web, ssh, file sharing, dns, phones (62078), printers...
TIMEOUT = 0.35
THREADS = 64


def local_address():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            return s.getsockname()[0]
    except OSError:
        return None


def default_network(address):
    return ipaddress.ip_network(f"{address}/24", strict=False)


def allowed(network):
    """Only private ranges, and nothing bigger than a /22 (1022 addresses)."""
    return network.is_private and not network.is_loopback and network.prefixlen >= 22


def probe(address):
    """(address, [open ports]) - a device answers if any common port connects or actively refuses."""
    open_ports, answered = [], False
    for port in PORTS:
        try:
            with socket.create_connection((address, port), timeout=TIMEOUT):
                open_ports.append(port)
                answered = True
        except ConnectionRefusedError:
            answered = True                       # something is there; the port is just closed
        except OSError:
            pass
    return address, answered, open_ports


def read_arp():
    """{ip: mac} from the system's neighbour table (Linux)."""
    table = {}
    try:
        with open("/proc/net/arp", encoding="utf-8") as f:
            for line in f.read().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 4 and parts[3] != "00:00:00:00:00:00":
                    table[parts[0]] = parts[3]
    except OSError:
        pass
    return table


def hostname(address):
    try:
        return socket.gethostbyaddr(address)[0]
    except OSError:
        return ""


def guess_kind(ports):
    if 62078 in ports:
        return "Apple phone/tablet"
    if 445 in ports or 139 in ports or 135 in ports:
        return "computer (file sharing)"
    if 22 in ports:
        return "computer/server (SSH)"
    if 80 in ports or 443 in ports or 8080 in ports:
        return "has a web page (router, printer, camera...)"
    if 53 in ports:
        return "router/DNS"
    return ""


def scan(network):
    hosts = [str(h) for h in network.hosts()]
    found = []
    with Progress(TextColumn("Scanning {task.description}"), BarColumn(), TextColumn("{task.completed}/{task.total}"), console=console,
                  transient=True) as progress:
        task = progress.add_task(str(network), total=len(hosts))
        with ThreadPoolExecutor(THREADS) as pool:
            for address, answered, ports in pool.map(probe, hosts):
                progress.advance(task)
                if answered:
                    found.append((address, ports))
    arp = read_arp()
    for address in hosts:                           # devices that ignored every port may still be in the neighbour table
        if address in arp and all(address != f[0] for f in found):
            found.append((address, []))
    return sorted(found, key=lambda f: ipaddress.ip_address(f[0])), arp


def main(args):
    if args:
        try:
            network = ipaddress.ip_network(args[0], strict=False)
        except ValueError:
            console.print("[red]Give a network like 192.168.1.0/24.[/red]")
            return
    else:
        mine = local_address()
        if not mine:
            console.print("[yellow]You do not appear to be on a network.[/yellow]")
            return
        network = default_network(mine)
    if not allowed(network):
        console.print("[bold red]Only private local networks (up to /22) can be scanned here.[/bold red]")
        return
    console.print(f"Scanning {network} ({network.num_addresses - 2} addresses). Only devices on your own network will answer.")
    found, arp = scan(network)
    mine = local_address()
    table = Table(header_style="bold blue", title=f"{len(found)} device(s) found")
    for col in ("Address", "Name", "Hardware address", "Looks like", "Open ports"):
        table.add_column(col)
    for address, ports in found:
        table.add_row(address + (" (this device)" if address == mine else ""), hostname(address), arp.get(address, ""),
                      guess_kind(ports), ", ".join(map(str, ports)))
    console.print(table)
    console.print("[dim]Phones and some devices hide from scans, so this list can miss some.[/dim]")


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
