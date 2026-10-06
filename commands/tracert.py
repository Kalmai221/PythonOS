"""tracert: show the path packets take to a host, one router at a time.

    tracert example.com
    tracert -m 15 example.com        give up after 15 hops (default 30)
"""
import os
import socket

from rich.console import Console
from rich.markup import escape

from pyos import netprobe

console = Console()
config = {"name": "tracert", "description": "Show the route to a host, hop by hop (tracert [-m max hops] <host>).", "alias": ["traceroute"]}


def parse(args):
    host, hops = None, 30
    args = list(args or [])
    i = 0
    while i < len(args):
        if args[i] == "-m" and i + 1 < len(args) and args[i + 1].isdigit():
            hops = max(1, min(64, int(args[i + 1])))
            i += 2
        elif args[i].startswith("-") or host is not None:
            return None
        else:
            host = args[i]
            i += 1
    return (host, hops) if host else None


def first_working(address, timeout):
    """(the probe function that works on this system, None), or (None, a text listing why each way failed). Some ways need rights the
    system may not give a program, so each is tried with a probe at TTL 64."""
    problems = []
    for method in netprobe.methods():
        try:
            method(address, 64, timeout)
            return method, None
        except (OSError, AttributeError, ImportError) as e:
            problems.append(f"{method.__name__.replace('probe_', '')}: {e}")
    return None, "; ".join(problems)


def execute(args=None):
    plan = parse(args)
    if plan is None:
        console.print("[bold red]Usage:[/bold red] tracert [-m max hops] <host>   for example: tracert example.com")
        return False
    host, max_hops = plan
    try:
        address = socket.gethostbyname(host)
    except OSError:
        console.print(f"[bold red]tracert: {host}: cannot find that name (no internet, or a misspelt address)[/bold red]")
        return False
    method, problem = first_working(address, 2)
    if method is None:
        android = "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ
        console.print("[bold red]tracert: this system does not let PythonOS send those probes.[/bold red]")
        console.print(f"[dim]{escape(problem)}[/dim]")
        if android:
            console.print("Android only lets an app send the probes tracert needs on some versions and devices. You can still check that a host "
                          "answers and how fast with [bold]ping[/bold], and look up its address with [bold]nslookup[/bold].")
        else:
            console.print("Try it as an administrator (Windows) or as root.")
        return False
    console.print(f"Route to {host} [{address}], at most {max_hops} hops:\n", highlight=False)
    try:
        for ttl in range(1, max_hops + 1):
            cells, who, reached = [], None, False
            for _ in range(3):
                kind, found, ms = method(address, ttl, 2)
                if kind == "timeout":
                    cells.append("   *   ")
                else:
                    who = found
                    reached = reached or kind == "done"
                    cells.append(f"{ms:6.1f} ms")
            console.print(f"{ttl:>3}  {'  '.join(cells)}  {who or 'no answer'}", highlight=False)
            if reached:
                console.print("\nReached the destination.")
                return True
    except KeyboardInterrupt:
        console.print()
    except OSError as e:
        console.print(f"[bold red]tracert: {e}[/bold red]")
        return False
    console.print(f"\nGave up after {max_hops} hops (some routers do not answer).")
    return True
