"""ping: see whether a computer answers, and how fast.

    ping <host>               four tries
    ping -c 10 <host>         ten tries
    ping -p 80 <host>         use another port (default 443, then 80)
    ping host:8080            the same, written as host:port

It times a TCP connection, not an ICMP echo, so it needs no special rights and works on every export. Ctrl+C stops and shows the summary.
"""
import socket
import time

from rich.console import Console

console = Console()
config = {"name": "ping", "description": "Check that a host answers and how fast (ping [-c count] [-p port] <host>)."}


def parse(args):
    """(host, port or None, count, timeout) from the arguments, or None when they are wrong."""
    host, port, count, timeout = None, None, 4, 3.0
    args = list(args or [])
    i = 0
    while i < len(args):
        word = args[i]
        if word in ("-c", "-p", "-W") and i + 1 < len(args) and args[i + 1].isdigit():
            value = int(args[i + 1])
            if word == "-c":
                count = max(1, min(100, value))
            elif word == "-p":
                port = value if 0 < value < 65536 else None
            else:
                timeout = max(1, min(30, value))
            i += 2
            continue
        if word.startswith("-") or host is not None:
            return None
        host = word
        i += 1
    if not host:
        return None
    for scheme in ("https://", "http://"):
        if host.startswith(scheme):
            host = host[len(scheme):]
            port = port or (443 if scheme == "https://" else 80)
    host = host.split("/")[0]
    if host.count(":") == 1:
        host, _, text = host.partition(":")
        if text.isdigit() and 0 < int(text) < 65536:
            port = int(text)
        else:
            return None
    return (host, port, count, timeout) if host else None


def tcp_time(address, port, timeout):
    """Milliseconds to open a connection, or None when it did not answer."""
    start = time.perf_counter()
    try:
        with socket.create_connection((address, port), timeout=timeout):
            pass
    except OSError:
        return None
    return (time.perf_counter() - start) * 1000


def summary(times, sent):
    """The summary lines for the answers (`times`, in ms) out of `sent` tries."""
    lost = sent - len(times)
    lines = [f"{sent} sent, {len(times)} answered, {lost * 100 // sent if sent else 0}% lost"]
    if times:
        lines.append(f"min/avg/max = {min(times):.1f}/{sum(times) / len(times):.1f}/{max(times):.1f} ms")
    return lines


def execute(args=None):
    plan = parse(args)
    if plan is None:
        console.print("[bold red]Usage:[/bold red] ping [-c count] [-p port] <host>   for example: ping example.com")
        return False
    host, port, count, timeout = plan
    try:
        address = socket.gethostbyname(host)
    except OSError:
        console.print(f"[bold red]ping: {host}: cannot find that name (no internet, or a misspelt address)[/bold red]")
        return False
    ports = [port] if port else [443, 80]
    console.print(f"PING {host} ({address}) port {port or '443/80'}", highlight=False)
    times, sent = [], 0
    try:
        for number in range(1, count + 1):
            sent += 1
            took = None
            for candidate in ports:
                took = tcp_time(address, candidate, timeout)
                if took is not None:
                    break
            if took is None:
                console.print(f"[red]no answer[/red] from {address}  (try {number})")
            else:
                times.append(took)
                console.print(f"answer from {address}: try={number} time={took:.1f} ms")
            if number < count:
                time.sleep(1)
    except KeyboardInterrupt:
        console.print()
    console.print(f"--- {host} ---")
    for line in summary(times, sent):
        console.print(line, highlight=False)
    return bool(times)
