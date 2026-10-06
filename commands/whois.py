"""whois: who registered a domain."""
import re
import socket

from rich.console import Console

console = Console()
config = {"name": "whois", "description": "Show the registration record of a domain (whois <domain>)."}


def ask(server, query, timeout=8):
    with socket.create_connection((server, 43), timeout=timeout) as sock:
        sock.sendall(query.encode("ascii", "ignore") + b"\r\n")
        sock.settimeout(timeout)
        data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
            if len(data) > 200000:
                break
    return data.decode("utf-8", "replace")


def referral(text):
    """The more specific whois server named in an answer of the root server, or None."""
    match = re.search(r"^\s*(?:refer|whois):\s*(\S+)", text, re.M | re.I)
    return match.group(1) if match else None


def valid(name):
    return bool(re.fullmatch(r"[A-Za-z0-9.-]{1,253}", name)) and "." in name


def execute(args=None):
    if not args or not valid(args[0]):
        console.print("[bold red]Usage:[/bold red] whois <domain>   for example: whois example.com")
        return False
    name = args[0]
    try:
        text = ask("whois.iana.org", name)
        server = referral(text)
        if server:
            text = ask(server, name)
    except OSError as e:
        console.print(f"[bold red]whois: could not reach the whois service ({e})[/bold red]")
        return False
    lines = [l for l in text.splitlines() if l.strip() and not l.startswith(("%", "#", ">>>"))]
    for line in lines[:60]:
        console.print(line, markup=False, highlight=False)
    if len(lines) > 60:
        console.print(f"... {len(lines) - 60} more lines", markup=False)
    return True
