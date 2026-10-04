#!/usr/bin/env python3
"""Network tools: check your connection, look up a name, test one port, time a web page, find your public address."""
import socket
import statistics
import sys
import time

import requests
from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt
from rich.table import Table

console = Console()
COMMON_PORTS = {22: "SSH", 25: "SMTP", 53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 465: "SMTPS",
                587: "SMTP (submission)", 993: "IMAPS", 3306: "MySQL", 5432: "PostgreSQL", 8080: "HTTP (alt)"}


def local_address():
    """The address this device uses on its network (no traffic is sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            return s.getsockname()[0]
    except OSError:
        return "unknown"


def check_connection():
    table = Table(title="Connection check", header_style="bold blue")
    table.add_column("Check")
    table.add_column("Result")
    table.add_row("Local address", local_address())
    for label, host, port in (("Internet (1.1.1.1:53)", "1.1.1.1", 53), ("Internet (8.8.8.8:53)", "8.8.8.8", 53)):
        ms = connect_time(host, port)
        table.add_row(label, f"[green]reachable, {ms:.0f} ms[/green]" if ms is not None else "[red]unreachable[/red]")
    try:
        ip = socket.gethostbyname("example.com")
        table.add_row("DNS (example.com)", f"[green]works ({ip})[/green]")
    except OSError:
        table.add_row("DNS (example.com)", "[red]failed - names do not resolve[/red]")
    console.print(table)


def connect_time(host, port, timeout=3.0):
    """Milliseconds to open a TCP connection, or None."""
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return (time.perf_counter() - start) * 1000
    except OSError:
        return None


def lookup(name):
    try:
        info = socket.getaddrinfo(name, None)
    except OSError as e:
        console.print(f"[red]Could not resolve {escape(name)}: {escape(str(e))}[/red]")
        return
    addresses = sorted({i[4][0] for i in info})
    console.print(f"[bold]{escape(name)}[/bold]")
    for a in addresses:
        console.print(f"  {a}  [dim]{'IPv6' if ':' in a else 'IPv4'}[/dim]")
    try:
        console.print(f"  [dim]canonical name:[/dim] {socket.gethostbyaddr(addresses[0])[0]}")
    except OSError:
        pass


def port_check(host, port):
    ms = connect_time(host, port)
    service = COMMON_PORTS.get(port, "")
    console.print(f"{escape(host)}:{port} {f'({service}) ' if service else ''}-> "
                  + (f"[bold green]open[/bold green] ({ms:.0f} ms)" if ms is not None else "[bold red]closed or filtered[/bold red]"))


def tcp_ping(host, port=443, count=4):
    times = []
    for i in range(count):
        ms = connect_time(host, port)
        console.print(f"  {i + 1}: " + (f"{ms:.0f} ms" if ms is not None else "[red]no reply[/red]"))
        if ms is not None:
            times.append(ms)
        time.sleep(0.4)
    if times:
        console.print(f"[bold]{len(times)}/{count} replies[/bold], min {min(times):.0f} / avg {statistics.mean(times):.0f} / max {max(times):.0f} ms")
    else:
        console.print("[red]No replies.[/red]")


def web_check(url):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    start = time.perf_counter()
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "PythonOS-nettools/1.0"}, allow_redirects=True)
    except requests.RequestException as e:
        console.print(f"[red]Could not reach {escape(url)}: {escape(str(e)[:100])}[/red]")
        return
    elapsed = (time.perf_counter() - start) * 1000
    colour = "green" if response.ok else "red"
    console.print(f"[{colour}]{response.status_code} {escape(response.reason or '')}[/{colour}] in {elapsed:.0f} ms, "
                  f"{len(response.content) / 1024:.1f} KB" + (f", redirected to {escape(response.url)}" if response.history else ""))
    for header in ("server", "content-type", "last-modified"):
        if header in response.headers:
            console.print(f"  [dim]{header}:[/dim] {escape(response.headers[header])}")


def public_address():
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            text = requests.get(url, timeout=6).text.strip()
            if text and len(text) < 50:
                console.print(f"Public address: [bold]{escape(text)}[/bold]   [dim](local: {local_address()})[/dim]")
                return
        except requests.RequestException:
            continue
    console.print("[red]Could not find the public address (are you online?).[/red]")


MENU = """[bold](c)[/bold]onnection check   [bold](l)[/bold]ookup name   [bold](p)[/bold]ort test   [bold](t)[/bold]cp ping
[bold](w)[/bold]eb page check   [bold](i)[/bold]p address   [bold](q)[/bold]uit"""


def main():
    while True:
        console.print(MENU)
        choice = Prompt.ask("Choose", choices=list("clptwiq"), default="c")
        if choice == "q":
            return
        if choice == "c":
            check_connection()
        elif choice == "i":
            public_address()
        elif choice == "l":
            lookup(Prompt.ask("Name").strip())
        elif choice == "p":
            host = Prompt.ask("Host").strip()
            port = Prompt.ask("Port", default="443").strip()
            if port.isdigit() and 0 < int(port) < 65536:
                port_check(host, int(port))
            else:
                console.print("[red]A port is a number from 1 to 65535.[/red]")
        elif choice == "t":
            tcp_ping(Prompt.ask("Host").strip())
        elif choice == "w":
            web_check(Prompt.ask("Address").strip())


def execute(args=None):
    args = list(args or [])
    try:
        if not args:
            main()
        elif args[0] == "check":
            check_connection()
        elif args[0] == "ip":
            public_address()
        elif args[0] == "lookup" and len(args) > 1:
            lookup(args[1])
        elif args[0] == "port" and len(args) > 2 and args[2].isdigit():
            port_check(args[1], int(args[2]))
        elif args[0] == "web" and len(args) > 1:
            web_check(args[1])
        elif args[0] == "ping" and len(args) > 1:
            tcp_ping(args[1])
        else:
            console.print("nettools [check | ip | lookup <name> | port <host> <port> | web <address> | ping <host>]")
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
