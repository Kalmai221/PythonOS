"""nslookup: ask the name servers about a name.

    nslookup example.com            addresses
    nslookup example.com MX         mail servers (A AAAA MX NS TXT CNAME SOA)
    nslookup 93.184.216.34          the name behind an address
    nslookup example.com A 8.8.8.8  ask a particular server
    nslookup example.com CAA        more record types (SRV CAA DS DNSKEY TLSA NAPTR SPF PTR ...) when the dnspython library is installed
"""
import re

from rich.console import Console

from pyos import dnsquery, optional

console = Console()
config = {"name": "nslookup", "description": "Look up a name in the DNS (nslookup <name> [type] [server]).", "alias": ["dig", "host"]}


MORE_TYPES = {"SRV", "CAA", "DS", "DNSKEY", "TLSA", "NAPTR", "SPF", "PTR", "HTTPS", "SVCB", "SSHFP", "LOC", "HINFO", "RP", "ANY"}


def lookup_more(name, qtype, server):
    """(owner, type, ttl, text) rows for a record type our own reader does not know, through dnspython. None when the library is missing."""
    dns = optional.get("dns.resolver")
    if dns is None:
        return None
    resolver = dns.Resolver(configure=False)
    resolver.nameservers = [server]
    resolver.lifetime = 6
    answer = resolver.resolve(name, qtype)
    return [(str(answer.rrset.name), qtype, answer.rrset.ttl, rdata.to_text()) for rdata in answer]


def parse(args):
    """(name, record type, server) from the arguments or None."""
    args = [a for a in (args or [])]
    if not args or len(args) > 3:
        return None
    name, qtype, server = args[0], "A", None
    for extra in args[1:]:
        if extra.upper() in dnsquery.TYPES or extra.upper() in MORE_TYPES:
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
    if qtype not in dnsquery.TYPES:
        return execute_more(name, qtype, server)
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


def execute_more(name, qtype, server):
    """A record type that needs dnspython."""
    try:
        rows = lookup_more(name, qtype, server)
    except Exception as e:                                               # noqa: BLE001 - dnspython raises its own errors: no such name, no answer, timeout
        label = type(e).__name__
        if label in ("NXDOMAIN",):
            console.print(f"[bold red]{name}: no such name[/bold red]")
        elif label in ("NoAnswer",):
            console.print(f"{name}: no {qtype} records")
            return True
        else:
            console.print(f"[bold red]nslookup: no answer from {server} ({label})[/bold red]")
        return False
    if rows is None:
        console.print(f"[yellow]nslookup: {qtype} records need the dnspython library (pip install dnspython).[/yellow]")
        return False
    console.print(f"Server: {server}", highlight=False)
    for owner, kind, ttl, text in rows:
        console.print(f"{owner:<30} {kind:<6} {text}  [dim](ttl {ttl}s)[/dim]", highlight=False)
    return True

