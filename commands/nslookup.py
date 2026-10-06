"""nslookup: ask the name servers about a name.

    nslookup example.com            addresses
    nslookup example.com MX         mail servers (A AAAA MX NS TXT CNAME SOA)
    nslookup 93.184.216.34          the name behind an address
    nslookup example.com A 8.8.8.8  ask a particular server
"""
import re

from rich.console import Console

from pyos import dnsquery

console = Console()
config = {"name": "nslookup", "description": "Look up a name in the DNS (nslookup <name> [type] [server]).", "alias": ["dig", "host"]}


def parse(args):
    """(name, record type, server) from the arguments or None."""
    args = [a for a in (args or [])]
    if not args or len(args) > 3:
        return None
    name, qtype, server = args[0], "A", None
    for extra in args[1:]:
        if extra.upper() in dnsquery.TYPES:
            qtype = extra.upper()
        elif re.fullmatch(r"\d+\.\d+\.\d+\.\d+", extra):
            server = extra
        else:
            return None
    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", name):
        name, qtype = dnsquery.reverse_name(name), "PTR"
    return name, qtype, server


def execute(args=None):
    plan = parse(args)
    if plan is None:
        console.print("[bold red]Usage:[/bold red] nslookup <name or address> [A|AAAA|MX|NS|TXT|CNAME|SOA] [server]")
        return False
    name, qtype, server = plan
    server = server or dnsquery.default_server()
    try:
        reply = dnsquery.query(name, qtype, server)
    except (OSError, ValueError) as e:
        console.print(f"[bold red]nslookup: no answer from {server} ({e})[/bold red]")
        return False
    console.print(f"Server: {server}", highlight=False)
    if reply["rcode"] != 0:
        console.print(f"[bold red]{name}: {dnsquery.RCODES.get(reply['rcode'], 'error ' + str(reply['rcode']))}[/bold red]")
        return False
    if not reply["answers"]:
        console.print(f"{name}: no {qtype} records")
        return True
    for owner, kind, ttl, text in reply["answers"]:
        console.print(f"{owner:<30} {kind:<6} {text}  [dim](ttl {ttl}s)[/dim]", highlight=False)
    return True
